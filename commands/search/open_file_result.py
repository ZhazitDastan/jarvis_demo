import ctypes
import sys
import importlib.util
import pathlib
import subprocess
import os


def _open_foreground(path: str) -> None:
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)
    except Exception:
        pass
    subprocess.Popen(
        f'start "" "{path}"',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

_BLOCKED_EXTS = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1",
                 ".vbs", ".wsf", ".scr", ".pif", ".cpl", ".hta"}

COMMAND_NAME = "open_file_result"
DESCRIPTION = (
    "Открыть файл или папку из последних результатов поиска по номеру. "
    "Примеры: 'открой первый', 'открой папку второго', 'второй'."
)
PARAMETERS = {
    "number": {
        "type": "integer",
        "description": "Номер файла: 1 (первый), 2 (второй), 3 (третий), 4, 5",
    },
    "action": {
        "type": "string",
        "description": "open — открыть файл, folder — открыть папку с файлом",
        "enum": ["open", "folder"],
    },
}
REQUIRED = ["number"]

_HERE = pathlib.Path(__file__).parent
_STATE_KEY = "_jarvis_search_state"


def _get_state():
    if _STATE_KEY not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _STATE_KEY, _HERE / "_state.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_STATE_KEY] = mod
        spec.loader.exec_module(mod)
    return sys.modules[_STATE_KEY]


def handler(number: int, action: str = "open") -> str:
    state = _get_state()
    results = state.get_results()

    if not results:
        return "Нет результатов поиска. Сначала найди файл."

    idx = number - 1
    if idx < 0 or idx >= len(results):
        return f"Нет файла с номером {number}. Найдено {len(results)} файлов."

    item = results[idx]
    path = item["path"]
    name = item["name"]

    if not os.path.exists(path):
        return f"Файл «{name}» больше не существует по пути {path}."

    ext = pathlib.Path(path).suffix.lower()
    if action == "open" and ext in _BLOCKED_EXTS:
        return f"Открытие исполняемых файлов ({ext}) заблокировано."

    try:
        if action == "folder":
            if item.get("category") == "folder":
                _open_foreground(path)
                return f"Открываю папку «{name}»."
            else:
                try:
                    ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)
                except Exception:
                    pass
                subprocess.Popen(
                    f'explorer /select,"{path}"',
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return f"Открываю папку с файлом «{name}»."
        else:
            _open_foreground(path)
            return f"Открываю «{name}»."
    except Exception as e:
        return f"Не удалось открыть «{name}»: {e}"