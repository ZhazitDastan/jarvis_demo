import subprocess
import winreg
import config

COMMAND_NAME = "do_not_disturb"
DESCRIPTION = (
    "Toggle Focus Assist / Do Not Disturb mode / "
    "Переключить режим «Не беспокоить» (Focus Assist). "
    "RU triggers: включи режим не беспокоить, выключи не беспокоить, "
    "тихий режим, режим фокуса, не беспокой меня. "
    "EN triggers: enable do not disturb, disable do not disturb, "
    "focus mode, focus assist, quiet mode."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["enable", "disable", "toggle"],
        "description": "enable — включить, disable — выключить, toggle — переключить.",
    }
}
REQUIRED = []

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
_REG_VALUE = "NOF_FOCUS_ASSIST_MANUAL_TURN_ON_CHANGE"


def _get_state() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            val, _ = winreg.QueryValueEx(key, _REG_VALUE)
            return bool(val)
    except FileNotFoundError:
        return False


def _set_state(enabled: bool):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH,
                            access=winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_DWORD, 1 if enabled else 0)
    except Exception:
        pass


def handler(action: str = "toggle") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    try:
        current = _get_state()
        if action == "toggle":
            target = not current
        else:
            target = action == "enable"

        _set_state(target)

        if target:
            return "Do Not Disturb enabled." if is_en else "Режим «Не беспокоить» включён."
        return "Do Not Disturb disabled." if is_en else "Режим «Не беспокоить» выключен."

    except Exception:
        # Fallback — открываем настройки уведомлений
        subprocess.Popen(["start", "ms-settings:notifications"], shell=True)
        return "Opening notification settings." if is_en else "Открываю настройки уведомлений."