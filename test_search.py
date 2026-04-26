import platform
import psutil
import subprocess
import json


def get_cpu_info() -> dict:
    info = {
        "name":         platform.processor() or "Unknown",
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical":  psutil.cpu_count(logical=True),
        "freq_max_mhz":   None,
        "freq_current_mhz": None,
    }
    freq = psutil.cpu_freq()
    if freq:
        info["freq_max_mhz"]     = round(freq.max)
        info["freq_current_mhz"] = round(freq.current)
    return info


def get_ram_info() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total_gb":     round(mem.total / 1024 ** 3, 1),
        "available_gb": round(mem.available / 1024 ** 3, 1),
        "used_gb":      round(mem.used / 1024 ** 3, 1),
        "percent":      mem.percent,
    }


def get_disk_info() -> list[dict]:
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device":     part.device,
                "mountpoint": part.mountpoint,
                "fstype":     part.fstype,
                "total_gb":   round(usage.total / 1024 ** 3, 1),
                "used_gb":    round(usage.used  / 1024 ** 3, 1),
                "free_gb":    round(usage.free  / 1024 ** 3, 1),
                "percent":    usage.percent,
            })
        except PermissionError:
            continue
    return disks


def get_gpu_info() -> list[dict]:
    gpus = []

    # NVIDIA через nvidia-smi
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,memory.used,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 5:
                    gpus.append({
                        "vendor":         "NVIDIA",
                        "name":           parts[0],
                        "vram_total_mb":  int(parts[1]),
                        "vram_free_mb":   int(parts[2]),
                        "vram_used_mb":   int(parts[3]),
                        "driver_version": parts[4],
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # AMD через rocm-smi (если есть)
    if not gpus:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for card, info in data.items():
                    gpus.append({
                        "vendor": "AMD",
                        "name":   info.get("Card Series", card),
                        "raw":    info,
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    # Fallback — через wmic на Windows
    if not gpus:
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get",
                 "Name,AdapterRAM,DriverVersion", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                for line in lines[1:]:  # пропускаем заголовок
                    parts = line.split(",")
                    if len(parts) >= 4:
                        vram_bytes = int(parts[1]) if parts[1].isdigit() else 0
                        gpus.append({
                            "vendor":        "Unknown",
                            "name":          parts[3] if len(parts) > 3 else "Unknown",
                            "vram_total_mb": round(vram_bytes / 1024 ** 2),
                            "driver_version": parts[2] if len(parts) > 2 else "Unknown",
                        })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return gpus


def get_system_info() -> dict:
    return {
        "os":      platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
    }


def get_battery_info() -> dict | None:
    battery = psutil.sensors_battery()
    if battery is None:
        return None
    return {
        "percent":    round(battery.percent, 1),
        "plugged_in": battery.power_plugged,
        "time_left_min": round(battery.secsleft / 60) if battery.secsleft > 0 else None,
    }


def get_all_info() -> dict:
    return {
        "system":  get_system_info(),
        "cpu":     get_cpu_info(),
        "ram":     get_ram_info(),
        "disks":   get_disk_info(),
        "gpu":     get_gpu_info(),
        "battery": get_battery_info(),
    }


def print_report():
    info = get_all_info()

    print("=" * 50)
    print("SYSTEM INFO")
    print("=" * 50)
    s = info["system"]
    print(f"  OS:           {s['os']} {s['os_version']}")
    print(f"  Architecture: {s['architecture']}")
    print(f"  Hostname:     {s['hostname']}")

    print("\nCPU")
    print("-" * 50)
    c = info["cpu"]
    print(f"  Name:         {c['name']}")
    print(f"  Cores:        {c['cores_physical']} physical / {c['cores_logical']} logical")
    if c["freq_max_mhz"]:
        print(f"  Freq:         {c['freq_current_mhz']} MHz (max {c['freq_max_mhz']} MHz)")

    print("\nRAM")
    print("-" * 50)
    r = info["ram"]
    print(f"  Total:        {r['total_gb']} GB")
    print(f"  Used:         {r['used_gb']} GB ({r['percent']}%)")
    print(f"  Available:    {r['available_gb']} GB")

    print("\nGPU")
    print("-" * 50)
    if info["gpu"]:
        for g in info["gpu"]:
            print(f"  Name:         {g['name']}")
            if "vram_total_mb" in g:
                print(f"  VRAM:         {g['vram_total_mb']} MB")
            if "driver_version" in g:
                print(f"  Driver:       {g['driver_version']}")
    else:
        print("  GPU info not available")

    print("\nDISKS")
    print("-" * 50)
    for d in info["disks"]:
        print(f"  {d['device']} ({d['mountpoint']}) — {d['total_gb']} GB total, {d['free_gb']} GB free ({d['percent']}% used)")

    battery = info["battery"]
    if battery:
        print("\nBATTERY")
        print("-" * 50)
        status = "plugged in" if battery["plugged_in"] else "on battery"
        time_left = f", ~{battery['time_left_min']} min left" if battery["time_left_min"] else ""
        print(f"  {battery['percent']}% ({status}{time_left})")

    print("=" * 50)

    # Рекомендация для Whisper
    print("\nWHISPER RECOMMENDATION")
    print("-" * 50)
    ram_gb = info["ram"]["total_gb"]
    has_nvidia = any(g.get("vendor") == "NVIDIA" for g in info["gpu"])
    vram = max((g.get("vram_total_mb", 0) for g in info["gpu"]), default=0)

    if has_nvidia and vram >= 6000:
        print("  ✓ GPU detected with enough VRAM")
        print("  → Recommended: faster-whisper large-v3 (GPU)")
    elif has_nvidia and vram >= 3000:
        print("  ✓ GPU detected")
        print("  → Recommended: faster-whisper large-v3-turbo (GPU)")
    elif ram_gb >= 8:
        print("  ~ No NVIDIA GPU or not enough VRAM")
        print("  → Recommended: faster-whisper medium (CPU) or Whisper API")
    else:
        print("  ! Low RAM")
        print("  → Recommended: faster-whisper small (CPU) or Whisper API")


if __name__ == "__main__":
    print_report()