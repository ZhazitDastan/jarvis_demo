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
    "Open a file or folder from the last search results by number. "
    "/ Открыть файл или папку из последних результатов поиска по номеру. "
    "RU: 'открой первый' → 1; 'открой второй' → 2; 'открой восьмой' → 8; "
    "'открой последний' → -1; 'открой максимальный' → -1; 'открой папку второго' → number=2 action=folder. "
    "EN: 'open first' → 1; 'open second' → 2; 'open the last one' → -1; 'open folder of third' → number=3 action=folder. "
    "Use number=-1 for last/последний/максимальный."
)
PARAMETERS = {
    "number": {
        "type": "integer",
        "description": (
            "1-based index of the file to open. "
            "Use -1 for last/последний/максимальный. "
            "Examples: 1=first/первый, 2=second/второй, ..., 8=eighth/восьмой, -1=last/последний."
        ),
    },
    "action": {
        "type": "string",
        "description": "open — открыть файл / open file, folder — открыть папку с файлом / show in folder",
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
    import config
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    state = _get_state()
    results = state.get_results()

    if not results:
        return "No search results. Search for a file first." if is_en else \
               "Нет результатов поиска. Сначала найди файл."

    # -1 → последний/last
    if number == -1 or number == 0:
        idx = len(results) - 1
    else:
        idx = number - 1

    if idx < 0 or idx >= len(results):
        return (f"No file #{number}. Found {len(results)} files.") if is_en else \
               (f"Нет файла с номером {number}. Найдено {len(results)} файлов.")

    item = results[idx]
    path = item["path"]
    name = item["name"]

    if not os.path.exists(path):
        return (f"File '{name}' no longer exists.") if is_en else \
               (f"Файл «{name}» больше не существует.")

    ext = pathlib.Path(path).suffix.lower()
    if action == "open" and ext in _BLOCKED_EXTS:
        return (f"Opening executable files ({ext}) is blocked.") if is_en else \
               (f"Открытие исполняемых файлов ({ext}) заблокировано.")

    try:
        if action == "folder":
            if item.get("category") == "folder":
                _open_foreground(path)
                return (f"Opening folder '{name}'.") if is_en else \
                       (f"Открываю папку «{name}».")
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
                return (f"Showing '{name}' in folder.") if is_en else \
                       (f"Открываю папку с файлом «{name}».")
        else:
            _open_foreground(path)
            return (f"Opening '{name}'.") if is_en else \
                   (f"Открываю «{name}».")
    except Exception as e:
        return (f"Failed to open '{name}': {e}") if is_en else \
               (f"Не удалось открыть «{name}»: {e}")