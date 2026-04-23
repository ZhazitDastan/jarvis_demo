import subprocess
import os

COMMAND_NAME = "open_telegram"
DESCRIPTION = "Открыть Telegram"
PARAMETERS = {}
REQUIRED = []

_TELEGRAM_PATHS = [
    os.path.join(os.environ.get("APPDATA", ""), "Telegram Desktop", "Telegram.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Telegram Desktop", "Telegram.exe"),
]


def handler() -> str:
    for path in _TELEGRAM_PATHS:
        if os.path.exists(path):
            subprocess.Popen([path])
            return "Открываю Telegram"
    try:
        subprocess.Popen(["telegram"], shell=True)
        return "Открываю Telegram"
    except Exception:
        return "Telegram не найден на этом компьютере"