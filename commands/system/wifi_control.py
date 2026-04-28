import subprocess
import config

COMMAND_NAME = "wifi_control"
DESCRIPTION = (
    "Wi-Fi control / Управление Wi-Fi. "
    "RU triggers: включи вайфай/wifi, выключи вайфай, покажи сети, "
    "подключись к [сеть], отключись от вайфай. "
    "EN triggers: enable wifi, disable wifi, show networks, "
    "connect to [network], disconnect wifi. "
    "action values: enable, disable, scan, connect, disconnect. "
    "ssid: network name — only for action=connect."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["enable", "disable", "scan", "connect", "disconnect"],
        "description": (
            "enable — включить Wi-Fi; disable — выключить; "
            "scan — список доступных сетей; "
            "connect — подключиться (нужен ssid); "
            "disconnect — отключиться от текущей сети."
        ),
    },
    "ssid": {
        "type": "string",
        "description": "Название Wi-Fi сети для подключения (только при action=connect).",
    },
}
REQUIRED = ["action"]

_RU = {
    "enabled":       "Wi-Fi включён.",
    "disabled":      "Wi-Fi выключен.",
    "disconnected":  "Отключился от Wi-Fi.",
    "no_ssid":       "Укажи название сети для подключения.",
    "connecting":    "Подключаюсь к сети",
    "connect_ok":    "Подключился к сети",
    "connect_fail":  "Не удалось подключиться к сети",
    "no_networks":   "Доступных Wi-Fi сетей не найдено.",
    "networks":      "Доступные сети",
    "admin_needed":  "Для этого нужны права администратора.",
    "error":         "Ошибка управления Wi-Fi",
}
_EN = {
    "enabled":       "Wi-Fi enabled.",
    "disabled":      "Wi-Fi disabled.",
    "disconnected":  "Disconnected from Wi-Fi.",
    "no_ssid":       "Please specify a network name to connect.",
    "connecting":    "Connecting to network",
    "connect_ok":    "Connected to network",
    "connect_fail":  "Failed to connect to network",
    "no_networks":   "No Wi-Fi networks found.",
    "networks":      "Available networks",
    "admin_needed":  "Administrator rights are required for this.",
    "error":         "Wi-Fi control error",
}


def _run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        args, capture_output=True, text=True,
        encoding="cp866", errors="replace",
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def _wifi_iface() -> str:
    """Возвращает имя Wi-Fi интерфейса из netsh."""
    _, out = _run(["netsh", "interface", "show", "interface"])
    for line in out.splitlines():
        lower = line.lower()
        if "wi-fi" in lower or "wireless" in lower or "wlan" in lower or "беспровод" in lower:
            parts = line.split()
            if parts:
                return parts[-1]
    return "Wi-Fi"


def handler(action: str = "scan", ssid: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    t = _EN if is_en else _RU

    try:
        if action == "enable":
            iface = _wifi_iface()
            code, out = _run(["netsh", "interface", "set", "interface", iface, "enable"])
            if code != 0 and "access" in out.lower():
                return t["admin_needed"]
            return t["enabled"]

        if action == "disable":
            iface = _wifi_iface()
            code, out = _run(["netsh", "interface", "set", "interface", iface, "disable"])
            if code != 0 and "access" in out.lower():
                return t["admin_needed"]
            return t["disabled"]

        if action == "disconnect":
            _run(["netsh", "wlan", "disconnect"])
            return t["disconnected"]

        if action == "connect":
            if not ssid:
                return t["no_ssid"]
            _run(["netsh", "wlan", "connect", f"name={ssid}"])
            return f"{t['connect_ok']} {ssid}."

        # scan
        _, out = _run(["netsh", "wlan", "show", "networks"])
        names = []
        for line in out.splitlines():
            if "SSID" in line and "BSSID" not in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name = parts[1].strip()
                    if name:
                        names.append(name)
        if not names:
            return t["no_networks"]
        joined = ", ".join(names[:6])
        return f"{t['networks']}: {joined}."

    except Exception as e:
        return f"{t['error']}: {e}"