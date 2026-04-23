import subprocess

COMMAND_NAME = "clipboard_get"
DESCRIPTION = "Прочитать текст из буфера обмена и озвучить его"
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    try:
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True, encoding="utf-8",
        )
        text = result.stdout.strip()
        if not text:
            return "Буфер обмена пуст"
        if len(text) > 200:
            return f"В буфере: {text[:200]}… (текст обрезан)"
        return f"В буфере обмена: {text}"
    except Exception as e:
        return f"Не удалось прочитать буфер: {e}"