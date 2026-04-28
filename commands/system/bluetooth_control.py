import subprocess
import config

COMMAND_NAME = "bluetooth_control"
DESCRIPTION = (
    "Bluetooth control / Управление Bluetooth. "
    "RU triggers: включи блютус/bluetooth, выключи блютус, найди устройства bluetooth. "
    "EN triggers: enable bluetooth, disable bluetooth, scan bluetooth devices, find bluetooth devices. "
    "action values: enable, disable, scan."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["enable", "disable", "scan"],
        "description": (
            "enable — включить Bluetooth; "
            "disable — выключить Bluetooth; "
            "scan — найти ближайшие Bluetooth устройства."
        ),
    },
}
REQUIRED = ["action"]

# PowerShell-скрипт для переключения Bluetooth через Windows Radio API
_PS_TOGGLE = """
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
    $null = [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType=WindowsRuntime]
    $null = [Windows.Devices.Radios.RadioState, Windows.System.Devices, ContentType=WindowsRuntime]

    $getRadios  = [Windows.Devices.Radios.Radio].GetMethod("GetRadiosAsync")
    $radiosTask = $getRadios.Invoke($null, @())
    $radiosTask.AsTask().Wait()
    $radios = $radiosTask.GetResults()

    $bt = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth }
    if (-not $bt) { Write-Output "NOT_FOUND"; exit 0 }

    $state = if ($args[0] -eq "enable") {
        [Windows.Devices.Radios.RadioState]::On
    } else {
        [Windows.Devices.Radios.RadioState]::Off
    }
    $setTask = $bt.SetStateAsync($state)
    $setTask.AsTask().Wait()
    Write-Output "OK"
} catch {
    Write-Output "ERROR: $_"
}
"""


def _ps(script: str, *args) -> str:
    cmd = ["powershell", "-NoProfile", "-Command", script] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout + r.stderr).strip()


def handler(action: str = "scan") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    if action in ("enable", "disable"):
        out = _ps(_PS_TOGGLE, action)
        if "NOT_FOUND" in out:
            return (
                "Bluetooth adapter not found on this device."
                if is_en else
                "Bluetooth адаптер не найден на этом устройстве."
            )
        if "ERROR" in out:
            return (
                f"Failed to change Bluetooth state. Try from Settings."
                if is_en else
                f"Не удалось изменить состояние Bluetooth. Попробуй через Настройки."
            )
        state_word = ("enabled" if action == "enable" else "disabled") if is_en else \
                     ("включён" if action == "enable" else "выключен")
        return f"Bluetooth {state_word}." if is_en else f"Bluetooth {state_word}."

    # scan
    try:
        import asyncio

        async def _scan():
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=5.0)
            return devices

        devices = asyncio.run(_scan())
        if not devices:
            return (
                "No Bluetooth devices found nearby."
                if is_en else
                "Рядом не найдено Bluetooth устройств."
            )
        names = [d.name or d.address for d in devices[:6]]
        joined = ", ".join(names)
        return (
            f"Found {len(devices)} device(s): {joined}."
            if is_en else
            f"Найдено {len(devices)} устройств: {joined}."
        )

    except ImportError:
        return (
            "Install bleak to scan: pip install bleak"
            if is_en else
            "Для сканирования установи bleak: pip install bleak"
        )
    except Exception as e:
        return (
            f"Bluetooth scan error: {e}"
            if is_en else
            f"Ошибка сканирования Bluetooth: {e}"
        )