import subprocess

COMMAND_NAME = "open_vscode"
DESCRIPTION = "Открыть Visual Studio Code, опционально с указанной папкой или файлом"
PARAMETERS = {
    "path": {
        "type": "string",
        "description": "Путь к папке или файлу (необязательно)",
    }
}
REQUIRED = []


def handler(path: str = "") -> str:
    cmd = ["code"] + ([path] if path else [])
    try:
        subprocess.Popen(cmd, shell=True)
        return f"Открываю VS Code{' — ' + path if path else ''}"
    except Exception as e:
        return f"Не удалось открыть VS Code: {e}"