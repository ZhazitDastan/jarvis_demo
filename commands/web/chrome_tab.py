import subprocess
import config

COMMAND_NAME = "chrome_tab"
DESCRIPTION = (
    "Control Chrome browser tabs: open new, close, switch, reopen closed, duplicate / "
    "Управление вкладками Chrome: открыть, закрыть, переключить, восстановить, дублировать. "
    "RU triggers: новая вкладка, закрой вкладку, следующая вкладка, предыдущая вкладка, "
    "восстанови вкладку, дублируй вкладку, открой инкогнито. "
    "EN triggers: new tab, close tab, next tab, previous tab, reopen tab, duplicate tab, incognito."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "description": (
            "Действие: new / close / next / prev / reopen / duplicate / incognito"
        ),
    }
}
REQUIRED = ["action"]

_ACTIONS = {
    "new":       ["ctrl", "t"],
    "close":     ["ctrl", "w"],
    "next":      ["ctrl", "tab"],
    "prev":      ["ctrl", "shift", "tab"],
    "reopen":    ["ctrl", "shift", "t"],
    "duplicate": ["ctrl", "shift", "k"],   # через меню
    "incognito": ["ctrl", "shift", "n"],
}

_LABELS_RU = {
    "new":       "Открываю новую вкладку",
    "close":     "Закрываю вкладку",
    "next":      "Следующая вкладка",
    "prev":      "Предыдущая вкладка",
    "reopen":    "Восстанавливаю последнюю закрытую вкладку",
    "duplicate": "Дублирую вкладку",
    "incognito": "Открываю окно инкогнито",
}
_LABELS_EN = {
    "new":       "Opening new tab",
    "close":     "Closing tab",
    "next":      "Next tab",
    "prev":      "Previous tab",
    "reopen":    "Reopening last closed tab",
    "duplicate": "Duplicating tab",
    "incognito": "Opening incognito window",
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