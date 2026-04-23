import os
import datetime
import subprocess

COMMAND_NAME = "create_note"
DESCRIPTION = "Создать текстовую заметку и сохранить её на рабочий стол"
PARAMETERS = {
    "text": {
        "type": "string",
        "description": "Текст заметки",
    },
    "title": {
        "type": "string",
        "description": "Заголовок заметки (необязательно)",
    },
}
REQUIRED = ["text"]


def handler(text: str, title: str = "") -> str:
    now = datetime.datetime.now()
    filename = f"note_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desktop, filename)
    header = f"{title}\n{'─' * len(title)}\n" if title else ""
    content = f"{header}[{now.strftime('%d.%m.%Y %H:%M')}]\n\n{text}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    subprocess.Popen(["notepad.exe", path])
    return f"Заметка сохранена: {filename}"