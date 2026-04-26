import os
import subprocess
import pathlib

COMMAND_NAME = "open_quick_folder"
DESCRIPTION = (
    "Открыть стандартную папку пользователя в Проводнике. "
    "Доступны: downloads, documents, desktop, music, pictures, videos, home."
    )
PARAMETERS = {
    "folder": {
        "type": "string",
        "description": "загрузки/downloads, документы/documents, рабочий стол / desktop, "
                        "музыка/music, фото/pictures, видео/videos",
},
}
REQUIRED = ["folder"]

HOME = pathlib.Path.home()

_FOLDER_MAP = {
    # Русские алиасы
    "загрузки": HOME / "Downloads",
    "документы": HOME / "Documents",
    "рабочий стол": HOME / "Desktop",
    "музыка": HOME / "Music",
    "фото": HOME / "Pictures",
    "фотографии": HOME / "Pictures",
    "видео": HOME / "Videos",
    "домашняя": HOME,
    # Английские
    "downloads": HOME / "Downloads",
    "documents": HOME / "Documents",
    "desktop": HOME / "Desktop",
    "music": HOME / "Music",
    "pictures": HOME / "Pictures",
    "photos": HOME / "Pictures",
    "videos": HOME / "Videos",
    "home": HOME,
}


def handler(folder: str) -> str:
    key = folder.lower().strip()
    path = _FOLDER_MAP.get(key)

    if path is None:
        # Частичный поиск
        for alias, p in _FOLDER_MAP.items():
            if key in alias or alias in key:
                path = p
                break

    if path is None:
        known = ", ".join(sorted({str(p.name) for p in
                                  _FOLDER_MAP.values()}))
        return f"Не знаю папку «{folder}». Доступны: {known}."

    # OneDrive зеркало рабочего стола
    if not path.exists():
        onedrive = HOME / "OneDrive" / path.name
        if onedrive.exists():
            path = onedrive

    if not path.exists():
        return f"Папка «{path}» не найдена на этом компьютере."

    subprocess.Popen(["explorer", str(path)])
    return f"Открываю папку {path.name}."
