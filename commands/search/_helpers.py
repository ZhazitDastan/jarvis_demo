"""
Общие утилиты для команд поиска файлов.
Файл начинается с _ — не загружается как команда.
"""

import sys
import importlib.util
import pathlib
import re

_HERE      = pathlib.Path(__file__).parent
_STATE_KEY = "_jarvis_search_state"

ORDINALS_RU = ["Первый", "Второй", "Третий", "Четвёртый", "Пятый"]
ORDINALS_EN = ["First",  "Second", "Third",  "Fourth",    "Fifth"]

CAT_RU = {
    "folder":   "папок",
    "document": "документов",
    "photo":    "фотографий",
    "video":    "видео",
    "music":    "музыки",
    "archive":  "архивов",
    "code":     "файлов кода",
}

CAT_EN = {
    "folder":   "folders",
    "document": "documents",
    "photo":    "photos",
    "video":    "videos",
    "music":    "music files",
    "archive":  "archives",
    "code":     "code files",
}

RU_DRIVE = {
    "а": "A", "б": "B", "с": "C", "д": "D",
    "е": "E", "ф": "F", "г": "G", "х": "H",
    "и": "I", "й": "J", "к": "K", "л": "L",
    "м": "M", "н": "N", "о": "O", "п": "P",
    "р": "R", "т": "T", "у": "U", "в": "V",
}

_ALIASES: list[tuple[str, str, str]] = [
    ("папк",        "folder",   ""),
    ("каталог",     "folder",   ""),
    ("директори",   "folder",   ""),
    ("folder",      "folder",   ""),
    ("directory",   "folder",   ""),
    ("ворд",        "document", "docx"),
    ("word",        "document", "docx"),
    ("эксел",       "document", "xlsx"),
    ("excel",       "document", "xlsx"),
    ("таблиц",      "document", "xlsx"),
    ("spreadsheet", "document", "xlsx"),
    ("презентаци",  "document", "pptx"),
    ("powerpoint",  "document", "pptx"),
    ("пдф",         "document", "pdf"),
    ("документ",    "document", ""),
    ("document",    "document", ""),
    ("фото",        "photo",    ""),
    ("картинк",     "photo",    ""),
    ("изображени",  "photo",    ""),
    ("скриншот",    "photo",    ""),
    ("скрин",       "photo",    ""),
    ("screenshot",  "photo",    ""),
    ("photo",       "photo",    ""),
    ("picture",     "photo",    ""),
    ("image",       "photo",    ""),
    ("видео",       "video",    ""),
    ("фильм",       "video",    ""),
    ("video",       "video",    ""),
    ("movie",       "video",    ""),
    ("film",        "video",    ""),
    ("музык",       "music",    ""),
    ("песн",        "music",    ""),
    ("трек",        "music",    ""),
    ("music",       "music",    ""),
    ("song",        "music",    ""),
    ("audio",       "music",    ""),
    ("архив",       "archive",  ""),
    ("archive",     "archive",  ""),
    ("скрипт",      "code",     ""),
    ("script",      "code",     ""),
]


def auto_detect(query: str, category: str, extension: str):
    """Определяет category/extension из текста запроса если ИИ не передал."""
    if category and extension:
        return query, category, extension

    q_lower = query.lower()
    detected_cat = category
    detected_ext = extension

    for alias, cat, ext in _ALIASES:
        if alias in q_lower:
            if not detected_cat:
                detected_cat = cat
            if not detected_ext and ext:
                detected_ext = ext
            q_lower = q_lower.replace(alias, "").strip()

    return q_lower.strip(" -,."), detected_cat, detected_ext


def normalize_drive(drive: str, query: str = "") -> tuple[str, str]:
    """
    Нормализует букву диска и при необходимости извлекает её из query.
    Возвращает (drive, query) — query может быть очищен от упоминания диска.
    """
    if drive:
        drive = RU_DRIVE.get(drive.lower(), drive).upper().strip(": \\")

    if drive and len(drive) > 1:
        m = re.search(r'\b([a-zA-Zа-яА-Я])\b\s*$', drive)
        drive = RU_DRIVE.get(m.group(1).lower(), m.group(1)).upper() if m else ""

    if not drive and query:
        m = re.search(
            r'(?:в\s+папк[еи]|на\s+диск[еу]|диск|in\s+(?:drive|folder))\s+([a-zA-Zа-яА-Я])\b',
            query, re.IGNORECASE,
        )
        if m:
            drive = RU_DRIVE.get(m.group(1).lower(), m.group(1)).upper()
            query = re.sub(
                r'(?:в\s+папк[еи]|на\s+диск[еу]|диск|in\s+(?:drive|folder))\s+[a-zA-Zа-яА-Я]\b',
                '', query, flags=re.IGNORECASE,
            ).strip(" ,.")

    return drive, query


def get_state():
    if _STATE_KEY not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _STATE_KEY, _HERE / "_state.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_STATE_KEY] = mod
        spec.loader.exec_module(mod)
    return sys.modules[_STATE_KEY]


def format_results(results: list[dict], is_en: bool) -> str:
    """Форматирует список файлов в голосовой ответ."""
    ordinals = ORDINALS_EN if is_en else ORDINALS_RU

    if len(results) == 1:
        return (
            f"Found: {results[0]['name']}. Say 'open' to open it."
            if is_en else
            f"Нашёл: {results[0]['name']}. Скажи «открой» чтобы открыть."
        )

    if is_en:
        parts = [f"Found {len(results)} files."]
        for i, r in enumerate(results):
            parts.append(f"{ordinals[i]} — {r['name']}.")
        parts.append("Say 'first', 'second', and so on to open.")
    else:
        count_word = "файла" if len(results) <= 4 else "файлов"
        parts = [f"Нашёл {len(results)} {count_word}."]
        for i, r in enumerate(results):
            parts.append(f"{ordinals[i]} — {r['name']}.")
        parts.append("Скажи «первый», «второй» и так далее чтобы открыть.")
    return " ".join(parts)
