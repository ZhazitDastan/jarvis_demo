"""
commands.py — реестр команд Jarvis

Как добавить новую команду:
  1. Напиши функцию def cmd_something(args: dict) -> str
  2. Добавь её в словарь COMMANDS внизу файла
  3. GPT автоматически узнает о команде и сможет её вызывать

Функция должна:
  - принимать args: dict (параметры от GPT, могут быть пустые)
  - возвращать str — текст который Jarvis скажет вслух
"""

import os
import subprocess
import webbrowser
import datetime


# ── Команды ──────────────────────────────────────────────────────────────────

def cmd_open_browser(args: dict) -> str:
    """Открывает браузер с нужным сайтом."""
    url = args.get("url", "https://google.com")
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Открываю {url}"


def cmd_what_time(args: dict) -> str:
    """Говорит текущее время."""
    now = datetime.datetime.now()
    return f"Сейчас {now.strftime('%H:%M')}"


def cmd_open_notepad(args: dict) -> str:
    """Открывает Блокнот."""
    subprocess.Popen(["notepad.exe"])
    return "Открываю Блокнот"


def cmd_open_calculator(args: dict) -> str:
    """Открывает Калькулятор."""
    subprocess.Popen(["calc.exe"])
    return "Открываю Калькулятор"


def cmd_open_explorer(args: dict) -> str:
    """Открывает Проводник Windows."""
    path = args.get("path", "")
    subprocess.Popen(["explorer.exe", path] if path else ["explorer.exe"])
    return f"Открываю Проводник{' — ' + path if path else ''}"


def cmd_search_google(args: dict) -> str:
    """Ищет запрос в Google."""
    query = args.get("query", "")
    if not query:
        return "Не указан поисковый запрос"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Ищу в Google: {query}"


def cmd_volume_up(args: dict) -> str:
    """Увеличивает громкость системы."""
    # PowerShell команда для громкости на Windows
    script = "(New-Object -com WScript.Shell).SendKeys([char]175)"
    for _ in range(5):  # 5 нажатий = +5 делений
        subprocess.run(["powershell", "-command", script], capture_output=True)
    return "Громкость увеличена"


def cmd_volume_down(args: dict) -> str:
    """Уменьшает громкость системы."""
    script = "(New-Object -com WScript.Shell).SendKeys([char]174)"
    for _ in range(5):
        subprocess.run(["powershell", "-command", script], capture_output=True)
    return "Громкость уменьшена"


def cmd_volume_mute(args: dict) -> str:
    """Выключает/включает звук."""
    script = "(New-Object -com WScript.Shell).SendKeys([char]173)"
    subprocess.run(["powershell", "-command", script], capture_output=True)
    return "Звук переключён"


def cmd_screenshot(args: dict) -> str:
    """Делает скриншот экрана."""
    try:
        import pyautogui
        path = os.path.join(os.path.expanduser("~"), "Desktop", "screenshot.png")
        pyautogui.screenshot(path)
        return f"Скриншот сохранён на рабочий стол"
    except ImportError:
        return "Для скриншотов установите: pip install pyautogui"


# ── Реестр команд ─────────────────────────────────────────────────────────────
# Ключ = название команды (GPT будет вызывать по этому имени)
# description  — описание на русском (для системного промпта)
# description_en — описание на английском
# params       — параметры которые GPT может передать (для function calling)
# handler      — функция выше

COMMANDS: dict = {
    "open_browser": {
        "description":    "Открыть браузер с указанным сайтом",
        "description_en": "Open the browser with a specified website",
        "params": {
            "url": {"type": "string", "description": "URL сайта, например google.com"}
        },
        "handler": cmd_open_browser,
    },
    "what_time": {
        "description":    "Сказать текущее время",
        "description_en": "Tell the current time",
        "params": {},
        "handler": cmd_what_time,
    },
    "search_google": {
        "description":    "Найти что-то в Google",
        "description_en": "Search something on Google",
        "params": {
            "query": {"type": "string", "description": "Поисковый запрос"}
        },
        "handler": cmd_search_google,
    },
    "open_notepad": {
        "description":    "Открыть Блокнот",
        "description_en": "Open Notepad",
        "params": {},
        "handler": cmd_open_notepad,
    },
    "open_calculator": {
        "description":    "Открыть Калькулятор",
        "description_en": "Open Calculator",
        "params": {},
        "handler": cmd_open_calculator,
    },
    "open_explorer": {
        "description":    "Открыть Проводник Windows",
        "description_en": "Open Windows Explorer",
        "params": {
            "path": {"type": "string", "description": "Путь к папке (необязательно)"}
        },
        "handler": cmd_open_explorer,
    },
    "volume_up": {
        "description":    "Увеличить громкость",
        "description_en": "Increase system volume",
        "params": {},
        "handler": cmd_volume_up,
    },
    "volume_down": {
        "description":    "Уменьшить громкость",
        "description_en": "Decrease system volume",
        "params": {},
        "handler": cmd_volume_down,
    },
    "volume_mute": {
        "description":    "Выключить / включить звук",
        "description_en": "Mute / unmute system sound",
        "params": {},
        "handler": cmd_volume_mute,
    },
}


def execute_command(name: str, args: dict) -> str:
    """Выполняет команду по имени. Возвращает текст ответа."""
    if name not in COMMANDS:
        return f"Команда '{name}' не найдена."
    try:
        result = COMMANDS[name]["handler"](args)
        return result
    except Exception as e:
        return f"Ошибка при выполнении команды '{name}': {e}"


def build_tools_schema() -> list:
    """Строит список tools для OpenAI function calling."""
    from config import ACTIVE_LANGUAGE
    use_en = ACTIVE_LANGUAGE == "en"

    tools = []
    for name, meta in COMMANDS.items():
        description = meta.get("description_en" if use_en else "description", meta["description"])
        properties = {}
        required = []
        for param_name, param_info in meta.get("params", {}).items():
            properties[param_name] = {
                "type": param_info["type"],
                "description": param_info["description"],
            }

        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return tools