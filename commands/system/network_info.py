import socket
import subprocess
import config

COMMAND_NAME = "network_info"
DESCRIPTION = (
    "Show IP address and current Wi-Fi network / Показать IP адрес и текущую сеть Wi-Fi. "
    "RU triggers: мой ip адрес, к какой сети подключён, покажи сетевую информацию, "
    "какой у меня айпи, ip компьютера. "
    "EN triggers: my ip address, what network am I on, show network info, what is my ip."
)
PARAMETERS = {}
REQUIRED = []


def _get_wifi_ssid() -> str:
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="cp866", errors="replace", timeout=5,
        )
        for line in r.stdout.splitlines():
            if "SSID" in line and "BSSID" not in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except Exception:
        pass
    return ""


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        # Локальный IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "unavailable"

    ssid = _get_wifi_ssid()

    if is_en:
        parts = [f"Local IP: {local_ip}."]
        if ssid:
            parts.append(f"Wi-Fi network: {ssid}.")
        return " ".join(parts)

    parts = [f"Локальный IP: {local_ip}."]
    if ssid:
        parts.append(f"Подключён к сети: {ssid}.")
    return " ".join(parts)