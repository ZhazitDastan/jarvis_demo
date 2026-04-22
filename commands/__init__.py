"""
commands/__init__.py — автосборщик команд

Каждый файл в папке commands/ = одна команда.
Файл должен содержать:
  - COMMAND_NAME   : str   — имя команды (как GPT будет её вызывать)
  - DESCRIPTION    : str   — описание для GPT (на русском)
  - PARAMETERS     : dict  — JSON Schema параметров (можно {})
  - REQUIRED       : list  — список обязательных параметров
  - def handler(**kwargs) -> str  — функция-обработчик

Пример файла: commands/open_browser.py
"""

import importlib
import pkgutil
import pathlib

COMMANDS: dict = {}

_pkg_dir = pathlib.Path(__file__).parent

for _mod_info in pkgutil.iter_modules([str(_pkg_dir)]):
    if _mod_info.name.startswith("_"):
        continue
    try:
        _mod = importlib.import_module(f"commands.{_mod_info.name}")

        # Каждый файл описывает ровно одну команду
        name = getattr(_mod, "COMMAND_NAME", None)
        if not name:
            continue

        COMMANDS[name] = {
            "description": getattr(_mod, "DESCRIPTION", ""),
            "parameters":  getattr(_mod, "PARAMETERS",  {}),
            "required":    getattr(_mod, "REQUIRED",    []),
            "handler":     _mod.handler,
        }
        print(f"    [cmd] Загружена команда: {name}")

    except Exception as e:
        print(f"    [!] Ошибка загрузки команды из {_mod_info.name}: {e}")


def execute_command(name: str, args: dict) -> str:
    if name not in COMMANDS:
        return f"Команда '{name}' не найдена."
    try:
        result = COMMANDS[name]["handler"](**args)
        return str(result) if result is not None else "Выполнено."
    except Exception as e:
        return f"Ошибка при выполнении '{name}': {e}"


def build_tools_schema() -> list[dict]:
    tools = []
    for name, meta in COMMANDS.items():
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