import config

COMMAND_NAME = "chrome_navigate"
DESCRIPTION = (
    "Navigate Chrome: go back, forward, refresh, scroll to top or bottom / "
    "Навигация в Chrome: назад, вперёд, обновить, прокрутить вверх или вниз. "
    "RU triggers: назад, вперёд, обнови страницу, прокрути вверх, прокрути вниз, в начало страницы, в конец страницы. "
    "EN triggers: go back, go forward, refresh page, scroll to top, scroll to bottom."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "description": "back / forward / refresh / top / bottom / hard_refresh",
    }
}
REQUIRED = ["action"]

_ACTIONS = {
    "back":         ["alt", "left"],
    "forward":      ["alt", "right"],
    "refresh":      ["f5"],
    "hard_refresh": ["ctrl", "shift", "r"],
    "top":          ["ctrl", "home"],
    "bottom":       ["ctrl", "end"],
}

_LABELS_RU = {
    "back":         "Назад",
    "forward":      "Вперёд",
    "refresh":      "Страница обновлена",
    "hard_refresh": "Жёсткое обновление страницы",
    "top":          "Прокрутил в начало страницы",
    "bottom":       "Прокрутил в конец страницы",
}
_LABELS_EN = {
    "back":         "Going back",
    "forward":      "Going forward",
    "refresh":      "Page refreshed",
    "hard_refresh": "Hard refresh done",
    "top":          "Scrolled to top",
    "bottom":       "Scrolled to bottom",
}


def handler(action: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    action = action.lower().strip()
    keys = _ACTIONS.get(action)
    if not keys:
        return f"Unknown action: {action}" if is_en else f"Неизвестное действие: {action}"
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        labels = _LABELS_EN if is_en else _LABELS_RU
        return labels.get(action, action)
    except ImportError:
        return "Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"