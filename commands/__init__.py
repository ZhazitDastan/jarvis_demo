"""
commands/__init__.py — автосборщик команд

Каждый .py файл в commands/ или любой подпапке = одна команда (если не начинается с _).
Файл должен содержать:
  - COMMAND_NAME   : str
  - DESCRIPTION    : str
  - PARAMETERS     : dict  — JSON Schema параметров (можно {})
  - REQUIRED       : list
  - def handler(**kwargs) -> str
"""

import importlib.util
import pathlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

COMMANDS: dict = {}
_lock = threading.Lock()
_pkg_dir = pathlib.Path(__file__).parent
_file_mtimes: dict = {}  # str(path) -> mtime


# ── Загрузка одного файла ──────────────────────────────────────────────────────

def _load_command_file(path: pathlib.Path) -> None:
    if path.name.startswith("_"):
        return
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"    [!] Ошибка загрузки {path.name}: {e}")
        return

    name = getattr(mod, "COMMAND_NAME", None)
    if not name:
        return

    entry = {
        "description": getattr(mod, "DESCRIPTION", ""),
        "parameters":  getattr(mod, "PARAMETERS",  {}),
        "required":    getattr(mod, "REQUIRED",    []),
        "handler":     mod.handler,
    }
    with _lock:
        COMMANDS[name] = entry
        _file_mtimes[str(path)] = _mtime(path)
    print(f"    [cmd] Загружена команда: {name}")


def _mtime(path: pathlib.Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


# ── Начальная загрузка (параллельно) ──────────────────────────────────────────

_py_files = [
    p for p in sorted(_pkg_dir.rglob("*.py"))
    if p != pathlib.Path(__file__) and not p.name.startswith("_")
]

with ThreadPoolExecutor(max_workers=min(8, len(_py_files) or 1)) as _pool:
    list(_pool.map(_load_command_file, _py_files))


# ── Фоновый hot-reload (замечает новые / изменённые файлы) ────────────────────

def _watch() -> None:
    while True:
        time.sleep(3)
        for py in sorted(_pkg_dir.rglob("*.py")):
            if py == pathlib.Path(__file__) or py.name.startswith("_"):
                continue
            current_mtime = _mtime(py)
            with _lock:
                known_mtime = _file_mtimes.get(str(py))
            if known_mtime != current_mtime:
                _load_command_file(py)


threading.Thread(target=_watch, daemon=True, name="cmd-watcher").start()


# ── Публичный API ──────────────────────────────────────────────────────────────

def execute_command(name: str, args: dict) -> str:
    with _lock:
        cmd = COMMANDS.get(name)
    if cmd is None:
        return f"Команда '{name}' не найдена."
    try:
        result = cmd["handler"](**args)
        return str(result) if result is not None else "Выполнено."
    except Exception as e:
        return f"Ошибка при выполнении '{name}': {e}"


def build_tools_schema() -> list[dict]:
    with _lock:
        snapshot = list(COMMANDS.items())
    tools = []
    for name, meta in snapshot:
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": meta["description"],
                "parameters": {
                    "type": "object",
                    "properties": meta["parameters"],
                    "required": meta["required"],
                },
            },
        })
    return tools