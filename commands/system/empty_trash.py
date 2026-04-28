import subprocess
import config

COMMAND_NAME = "empty_trash"
DESCRIPTION = (
    "Empty the Recycle Bin / Очистить корзину. "
    "RU triggers: очисти корзину, пусти корзину, удали из корзины, очистить мусор. "
    "EN triggers: empty recycle bin, empty trash, clear recycle bin."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Clear-RecycleBin -Confirm:$false -ErrorAction SilentlyContinue"],
        capture_output=True, timeout=15,
    )
    if r.returncode == 0:
        return "Recycle Bin emptied." if is_en else "Корзина очищена."
    return "Recycle Bin is already empty or access denied." if is_en else "Корзина уже пуста или нет доступа."