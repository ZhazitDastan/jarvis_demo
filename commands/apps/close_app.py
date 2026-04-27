import subprocess
import importlib.util
import pathlib

COMMAND_NAME = "close_app"
DESCRIPTION = (
    "Закрыть (завершить) запущенное приложение по названию. "
    "Принимает русские и английские названия: "
    "телеграм/telegram, хром/chrome, дискорд/discord, спотифай/spotify, "
    "блокнот/notepad, калькулятор/calculator, vscode, стим/steam и другие. "
    "Используй эту команду когда пользователь говорит: закрой, выключи, останови приложение."
)
PARAMETERS = {
    "app": {
        "type": "string",
        "description": (
            "Название приложения на русском или английском. "
            "Примеры: телеграм, хром, дискорд, спотифай, блокнот, vscode, стим, firefox"
        ),
    },
    "force": {
        "type": "boolean",
        "description": "Принудительно завершить без запроса сохранения (по умолчанию false)",
    },
}
REQUIRED = ["app"]

_reg_path = pathlib.Path(__file__).parent / "_registry.py"
_spec = importlib.util.spec_from_file_location("_apps_registry", _reg_path)
_reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reg)


def handler(app: str, force: bool = False) -> str:
    import config
    en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    key = _reg.resolve(app)
    if key is None:
        return (f"Unknown app '{app}'." if en
                else f"Не знаю приложение «{app}».")

    process = _reg.APP_REGISTRY[key]["process"]
    flags = ["/F"] if force else []

    result = subprocess.run(
        ["taskkill"] + flags + ["/IM", process],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        return f"{key} closed" if en else f"{key} закрыт"
    if "not found" in result.stderr.lower() or "не найден" in result.stderr:
        return f"{key} is not running" if en else f"{key} не запущен"
    if not force:
        result2 = subprocess.run(
            ["taskkill", "/F", "/IM", process],
            capture_output=True, text=True,
        )
        if result2.returncode == 0:
            return f"{key} force closed" if en else f"{key} принудительно закрыт"
    return (f"Failed to close {key}: {result.stderr.strip()}" if en
            else f"Не удалось закрыть {key}: {result.stderr.strip()}")
