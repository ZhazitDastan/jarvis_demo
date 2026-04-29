import config

COMMAND_NAME = "chrome_zoom"
DESCRIPTION = (
    "Zoom Chrome in, out or reset to 100% / "
    "Изменить масштаб страницы Chrome: увеличить, уменьшить, сбросить. "
    "RU triggers: увеличь масштаб, уменьши масштаб, сбрось масштаб, масштаб сто процентов. "
    "EN triggers: zoom in, zoom out, reset zoom, zoom 100 percent."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "description": "in / out / reset",
    }
}
REQUIRED = ["action"]


def handler(action: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    action = action.lower().strip()
    try:
        import pyautogui
        if action == "in":
            pyautogui.hotkey("ctrl", "+")
            return "Zoom in" if is_en else "Масштаб увеличен"
        elif action == "out":
            pyautogui.hotkey("ctrl", "-")
            return "Zoom out" if is_en else "Масштаб уменьшен"
        elif action == "reset":
            pyautogui.hotkey("ctrl", "0")
            return "Zoom reset to 100%" if is_en else "Масштаб сброшен до 100%"
        else:
            return f"Unknown action: {action}" if is_en else f"Неизвестное действие: {action}"
    except ImportError:
        return "Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"