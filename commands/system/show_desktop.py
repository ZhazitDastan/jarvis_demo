import subprocess
import config

COMMAND_NAME = "show_desktop"
DESCRIPTION = (
    "Minimize all windows and show the desktop / Свернуть все окна и показать рабочий стол. "
    "RU triggers: покажи рабочий стол, сверни все окна, сверни всё. "
    "EN triggers: show desktop, minimize all windows, minimize all."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         "(New-Object -ComObject Shell.Application).ToggleDesktop()"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return "Desktop shown." if is_en else "Показываю рабочий стол."