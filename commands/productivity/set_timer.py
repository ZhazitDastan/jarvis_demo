import threading
import subprocess

COMMAND_NAME = "set_timer"
DESCRIPTION = "Поставить таймер на указанное количество минут и/или секунд"
PARAMETERS = {
    "minutes": {
        "type": "integer",
        "description": "Количество минут (необязательно)",
    },
    "seconds": {
        "type": "integer",
        "description": "Количество секунд (необязательно)",
    },
    "label": {
        "type": "string",
        "description": "Название таймера (необязательно), например 'чай готов'",
    },
}
REQUIRED = []


def _ring(total_seconds: int, label: str) -> None:
    import time
    time.sleep(total_seconds)
    title = "Jarvis — Таймер"
    msg = label if label else "Время вышло!"
    script = (
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"$n = New-Object System.Windows.Forms.NotifyIcon; "
        f"$n.Icon = [System.Drawing.SystemIcons]::Information; "
        f"$n.Visible = $true; "
        f"$n.ShowBalloonTip(8000, '{title}', '{msg}', "
        f"[System.Windows.Forms.ToolTipIcon]::Info); "
        f"Start-Sleep -Seconds 9; $n.Dispose()"
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def handler(minutes: int = 0, seconds: int = 0, label: str = "") -> str:
    total = int(minutes) * 60 + int(seconds)
    if total <= 0:
        return "Укажи время таймера, например: 5 минут или 30 секунд."
    threading.Thread(target=_ring, args=(total, label), daemon=True).start()
    parts = []
    if minutes:
        parts.append(f"{minutes} мин")
    if seconds:
        parts.append(f"{seconds} сек")
    suffix = f" «{label}»" if label else ""
    return f"Таймер установлен на {' '.join(parts)}{suffix}"