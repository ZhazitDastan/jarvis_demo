import config

COMMAND_NAME = "chrome_tools"
DESCRIPTION = (
    "Open Chrome tools: DevTools, bookmarks, history, downloads, find on page, address bar / "
    "Открыть инструменты Chrome: DevTools, закладки, история, загрузки, поиск по странице, адресная строка. "
    "RU triggers: открой devtools, открой инструменты разработчика, добавь в закладки, "
    "открой историю браузера, открой загрузки, найди на странице, открой адресную строку. "
    "EN triggers: open devtools, developer tools, add bookmark, open history, "
    "open downloads, find on page, open address bar."
)
PARAMETERS = {
    "tool": {
        "type": "string",
        "description": "devtools / bookmark / history / downloads / find / address_bar / settings",
    }
}
REQUIRED = ["tool"]

_TOOLS = {
    "devtools":    ["f12"],
    "bookmark":    ["ctrl", "d"],
    "history":     ["ctrl", "h"],
    "downloads":   ["ctrl", "j"],
    "find":        ["ctrl", "f"],
    "address_bar": ["ctrl", "l"],
    "settings":    [],   # handled separately
}

_LABELS_RU = {
    "devtools":    "Открываю DevTools",
    "bookmark":    "Добавляю в закладки",
    "history":     "Открываю историю",
    "downloads":   "Открываю загрузки",
    "find":        "Поиск по странице",
    "address_bar": "Адресная строка",
    "settings":    "Открываю настройки Chrome",
}
_LABELS_EN = {
    "devtools":    "Opening DevTools",
    "bookmark":    "Adding bookmark",
    "history":     "Opening history",
    "downloads":   "Opening downloads",
    "find":        "Find on page",
    "address_bar": "Address bar",
    "settings":    "Opening Chrome settings",
}


def handler(tool: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    tool = tool.lower().strip()
    try:
        import pyautogui

        if tool == "settings":
            pyautogui.hotkey("ctrl", "l")
            import time
            time.sleep(0.2)
            pyautogui.typewrite("chrome://settings/", interval=0.03)
            pyautogui.press("enter")
        else:
            keys = _TOOLS.get(tool)
            if not keys:
                return f"Unknown tool: {tool}" if is_en else f"Неизвестный инструмент: {tool}"
            pyautogui.hotkey(*keys)

        labels = _LABELS_EN if is_en else _LABELS_RU
        return labels.get(tool, tool)

    except ImportError:
        return "Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"