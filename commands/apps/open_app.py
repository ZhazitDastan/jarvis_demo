import subprocess
import importlib.util
import pathlib

COMMAND_NAME = "open_app"
DESCRIPTION = (
    "Открыть любое приложение по названию. "
    "Принимает русские и английские названия: "
    "телеграм/telegram, хром/chrome, дискорд/discord, спотифай/spotify, "
    "блокнот/notepad, калькулятор/calculator, проводник/explorer, "
    "vscode/редактор кода, стим/steam, ворд/word, ексель/excel и другие."
)
PARAMETERS = {
    "app": {
        "type": "string",
        "description": (
            "Название приложения на русском или английском. "
            "Примеры: телеграм, хром, дискорд, спотифай, блокнот, калькулятор, "
            "проводник, vscode, стим, ворд, ексель, firefox, edge, vlc"
        ),
    }
}
REQUIRED = ["app"]

# Загрузка реестра из соседнего файла _registry.py
_reg_path = pathlib.Path(__file__).parent / "_registry.py"
_spec = importlib.util.spec_from_file_location("_apps_registry", _reg_path)
_reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reg)


def handler(app: str) -> str:
    key = _reg.resolve(app)
    if key is None:
        known = ", ".join(sorted(_reg.APP_REGISTRY.keys()))
        return f"Не знаю приложение «{app}». Доступны: {known}"

    entry = _reg.APP_REGISTRY[key]
    cmd = entry["open"]
    shell = entry.get("shell", False)

    try:
        subprocess.Popen(cmd, shell=shell)
        return f"Открываю {key}"
    except FileNotFoundError:
        # Попытка через shell если прямой путь не найден
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Открываю {key}"
        except Exception as e:
            return f"Не удалось открыть {key}: {e}"