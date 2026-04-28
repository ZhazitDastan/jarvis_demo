import ctypes
import os
import config

COMMAND_NAME = "set_wallpaper"
DESCRIPTION = (
    "Set desktop wallpaper from a file path / Установить обои рабочего стола из файла. "
    "RU triggers: поставь обои, установи обои, смени обои, обои рабочего стола. "
    "EN triggers: set wallpaper, change wallpaper, set desktop background. "
    "path: full path to an image file (.jpg, .png, .bmp)."
)
PARAMETERS = {
    "path": {
        "type": "string",
        "description": "Полный путь к файлу изображения (.jpg, .png, .bmp) / Full path to image file.",
    }
}
REQUIRED = ["path"]

_ALLOWED = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE   = 0x0001
SPIF_SENDCHANGE      = 0x0002


def handler(path: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    if not path:
        return "Please specify an image path." if is_en else "Укажи путь к изображению."

    path = os.path.expanduser(path.strip('"').strip("'"))

    if not os.path.isfile(path):
        return (
            f"File not found: {path}"
            if is_en else
            f"Файл не найден: {path}"
        )

    ext = os.path.splitext(path)[1].lower()
    if ext not in _ALLOWED:
        return (
            f"Unsupported format: {ext}. Use JPG, PNG or BMP."
            if is_en else
            f"Неподдерживаемый формат: {ext}. Используй JPG, PNG или BMP."
        )

    abs_path = os.path.abspath(path)
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )

    if result:
        name = os.path.basename(abs_path)
        return f"Wallpaper set: {name}" if is_en else f"Обои установлены: {name}"
    return "Failed to set wallpaper." if is_en else "Не удалось установить обои."