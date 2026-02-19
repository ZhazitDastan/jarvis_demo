import os
import platform
import socket
import psutil
import subprocess
from datetime import datetime, timedelta


# ──────────────────────────────────────────
#  1. BASIC SYSTEM INFO
# ──────────────────────────────────────────

def get_os_info():
    """Get OS name, version, architecture and hostname"""
    print("\n=== OS Info ===")
    print(f"Hostname      : {socket.gethostname()}")
    print(f"OS            : {platform.system()} {platform.release()}")
    print(f"Version       : {platform.version()}")
    print(f"Architecture  : {platform.architecture()[0]}")


def get_cpu_info():
    """Get CPU model, cores and current load"""
    print("\n=== CPU Info ===")
    print(f"Processor     : {platform.processor()}")
    print(f"Physical cores: {psutil.cpu_count(logical=False)}")
    print(f"Logical cores : {psutil.cpu_count(logical=True)}")
    print(f"CPU Usage     : {psutil.cpu_percent(interval=1)}%")


def get_ram_info():
    """Get total, used and available RAM"""
    print("\n=== RAM Info ===")
    ram = psutil.virtual_memory()
    print(f"Total         : {ram.total / 1e9:.2f} GB")
    print(f"Used          : {ram.used / 1e9:.2f} GB")
    print(f"Available     : {ram.available / 1e9:.2f} GB")
    print(f"Usage         : {ram.percent}%")


def get_uptime():
    """Get system uptime"""
    print("\n=== Uptime ===")
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    print(f"Boot time     : {boot_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Uptime        : {str(timedelta(seconds=int(uptime.total_seconds())))}")


# ──────────────────────────────────────────
#  2. DISKS
# ──────────────────────────────────────────

def get_disk_info():
    """Get disk partitions, usage and file systems"""
    print("\n=== Disk Info ===")
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            print(f"\nDrive         : {part.device}")
            print(f"  Mount       : {part.mountpoint}")
            print(f"  File system : {part.fstype}")
            print(f"  Total       : {usage.total / 1e9:.2f} GB")
            print(f"  Used        : {usage.used / 1e9:.2f} GB")
            print(f"  Free        : {usage.free / 1e9:.2f} GB")
            print(f"  Usage       : {usage.percent}%")
        except PermissionError:
            print(f"  [No access to {part.mountpoint}]")


# ──────────────────────────────────────────
#  3. NETWORK
# ──────────────────────────────────────────

def get_network_info():
    """Get network adapters, IPs, MACs and connection status"""
    print("\n=== Network Info ===")

    # Local IP
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"Local IP      : {local_ip}")
    except:
        print("Local IP      : Unavailable")

    # Adapters
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface, addr_list in addrs.items():
        is_up = stats[iface].isup if iface in stats else False
        print(f"\nAdapter       : {iface} ({'UP' if is_up else 'DOWN'})")
        for addr in addr_list:
            if str(addr.family) in ("AddressFamily.AF_INET", "2"):
                print(f"  IPv4        : {addr.address}")
            elif str(addr.family) in ("AddressFamily.AF_PACKET", "17", "AddressFamily.AF_LINK"):
                print(f"  MAC         : {addr.address}")


def get_wifi_info():
    """Get Wi-Fi SSID and signal strength (Windows only)"""
    print("\n=== Wi-Fi Info ===")
    try:
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            encoding="utf-8", errors="ignore"
        )
        for line in result.splitlines():
            line = line.strip()
            if "SSID" in line and "BSSID" not in line:
                print(f"SSID          : {line.split(':', 1)[1].strip()}")
            elif "Signal" in line:
                print(f"Signal        : {line.split(':', 1)[1].strip()}")
            elif "State" in line:
                print(f"State         : {line.split(':', 1)[1].strip()}")
    except Exception as e:
        print(f"Wi-Fi info unavailable: {e}")


def get_network_speed():
    """Get current network upload/download speed"""
    print("\n=== Network Speed ===")
    net1 = psutil.net_io_counters()
    import time;
    time.sleep(1)
    net2 = psutil.net_io_counters()
    download = (net2.bytes_recv - net1.bytes_recv) / 1024
    upload = (net2.bytes_sent - net1.bytes_sent) / 1024
    print(f"Download      : {download:.2f} KB/s")
    print(f"Upload        : {upload:.2f} KB/s")


# ──────────────────────────────────────────
#  4. BATTERY & POWER
# ──────────────────────────────────────────

def get_battery_info():
    """Get battery level, status and estimated time"""
    print("\n=== Battery Info ===")
    battery = psutil.sensors_battery()
    if battery is None:
        print("No battery detected (desktop PC or unsupported)")
        return
    print(f"Charge        : {battery.percent:.1f}%")
    print(f"Power source  : {'AC (plugged in)' if battery.power_plugged else 'Battery'}")
    print(f"Status        : {'Charging' if battery.power_plugged else 'Discharging'}")
    if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft > 0:
        time_left = str(timedelta(seconds=battery.secsleft))
        label = "Time to full" if battery.power_plugged else "Time left"
        print(f"{label:<14}: {time_left}")


# ──────────────────────────────────────────
#  5. DEVICES
# ──────────────────────────────────────────

def get_usb_devices():
    """List connected USB devices (Windows only)"""
    print("\n=== USB Devices ===")
    try:
        result = subprocess.check_output(
            ["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent"],
            encoding="utf-8", errors="ignore"
        )
        devices = [line.strip() for line in result.splitlines() if "DeviceID" in line]
        if devices:
            for d in devices[:10]:  # limit output
                print(f"  {d}")
        else:
            print("No USB devices found or access denied")
    except Exception as e:
        print(f"Error: {e}")


def get_audio_devices():
    """List audio devices"""
    print("\n=== Audio Devices ===")
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetAllDevices()
        for d in devices:
            print(f"  {d.FriendlyName}")
    except Exception as e:
        print(f"pycaw not available: {e}")


# ──────────────────────────────────────────
#  6. PROCESSES
# ──────────────────────────────────────────

def get_top_processes(limit: int = 10):
    """Show top processes by CPU and RAM usage"""
    print(f"\n=== Top {limit} Processes (by CPU) ===")
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'nice']):
        try:
            procs.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sort by CPU
    procs = sorted(procs, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:limit]
    print(f"{'PID':<8} {'Name':<30} {'CPU%':<8} {'RAM%':<8} {'Priority'}")
    print("-" * 65)
    for p in procs:
        priority = p['nice'] if p['nice'] is not None else '-'
        print(f"{p['pid']:<8} {p['name'][:28]:<30} {p['cpu_percent']:<8} {p['memory_percent']:.1f}%   {priority}")


# ──────────────────────────────────────────
#  7. SECURITY
# ──────────────────────────────────────────

def get_security_info():
    """Get firewall and Windows Defender status (Windows only)"""
    print("\n=== Security Info ===")
    try:
        # Firewall
        fw = subprocess.check_output(
            ["netsh", "advfirewall", "show", "allprofiles", "state"],
            encoding="utf-8", errors="ignore"
        )
        for line in fw.splitlines():
            if "State" in line:
                print(f"Firewall      : {line.strip()}")
    except Exception as e:
        print(f"Firewall info unavailable: {e}")

    try:
        # Windows Defender
        wd = subprocess.check_output(
            ["powershell", "-Command",
             "Get-MpComputerStatus | Select-Object -Property RealTimeProtectionEnabled, AntivirusEnabled"],
            encoding="utf-8", errors="ignore"
        )
        print("Windows Defender:")
        for line in wd.splitlines():
            if line.strip():
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"Defender info unavailable: {e}")


def get_active_users():
    """List currently logged-in users"""
    print("\n=== Active Users ===")
    try:
        users = psutil.users()
        for u in users:
            print(
                f"  User: {u.name} | Terminal: {u.terminal} | Since: {datetime.fromtimestamp(u.started).strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        print(f"Error: {e}")


# ──────────────────────────────────────────
#  8. DISPLAY
# ──────────────────────────────────────────

def get_display_info():
    """Get screen resolution, refresh rate and monitor count"""
    print("\n=== Display Info ===")
    try:
        result = subprocess.check_output(
            ["powershell", "-Command",
             "Get-CimInstance -ClassName Win32_VideoController | Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate"],
            encoding="utf-8", errors="ignore"
        )
        print(result.strip())
    except Exception as e:
        print(f"Display info unavailable: {e}")


# ──────────────────────────────────────────
#  FULL SUMMARY
# ──────────────────────────────────────────

def get_full_info():
    """Print all system information"""
    get_os_info()
    get_cpu_info()
    get_ram_info()
    get_uptime()
    get_disk_info()
    get_battery_info()
    get_network_info()
    get_wifi_info()
    get_security_info()
    get_active_users()
    get_display_info()


# ──────────────────────────────────────────
#  CONSOLE
# ──────────────────────────────────────────

def show_help():
    print("""
========================================
       System Info Commands
========================================
  os           - OS, hostname, architecture
  cpu          - CPU model, cores, usage
  ram          - RAM total/used/free
  uptime       - System uptime
  disk         - Disk partitions and usage
  battery      - Battery status and time
  network      - Network adapters and IPs
  wifi         - Wi-Fi SSID and signal
  speed        - Network upload/download speed
  usb          - Connected USB devices
  audio        - Audio devices
  processes    - Top 10 processes by CPU
  security     - Firewall and antivirus status
  users        - Active logged-in users
  display      - Screen resolution and refresh rate
  info         - Full system summary
  help         - Show this help
  exit         - Exit program
========================================
    """)


