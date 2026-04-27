import sys
import importlib.util
import pathlib
import config

COMMAND_NAME = "search_files"
DESCRIPTION = (
    "Search for files and folders on the computer. "
    "/ Поиск файлов и папок на компьютере. "

    "RU triggers (call this command for): найди, ищи, поищи, поиск, найти, где файл, открой файл. "
    "EN triggers: find, search for, look for, locate, where is my file. "

    "CATEGORIES (use in 'category' field): "
    "folder — папка/каталог/folder/directory; "
    "document — документ/ворд/word/pdf/таблица/excel/презентация/powerpoint; "
    "photo — фото/фотографии/картинки/скриншот/скрин/screenshot/photo/picture/image; "
    "video — видео/фильм/video/movie/film; "
    "music — музыка/песни/треки/music/song/audio/mp3; "
    "archive — архив/archive/zip/rar; "
    "code — код/скрипт/code/script. "

    "DATE filter (date_filter): today, week, month, year. "
    "SIZE filter (size_filter): small (<1MB), medium (1-100MB), large (>100MB). "
    "DRIVE filter (drive): letter only, no colon — e.g. D, E, F. "

    "RU examples: "
    "'найди папку диплом' → category=folder query=диплом; "
    "'ищи файл диплом' → query=диплом; "
    "'ищи папку' → category=folder; "
    "'поищи скриншот' → category=photo query=скриншот; "
    "'найди ворд документы' → category=document extension=docx; "
    "'найди музыку за месяц' → category=music date_filter=month; "
    "'найди большие видео' → category=video size_filter=large; "
    "'ищи в диске д' → drive=D; "
    "'найди диплом на диске д' → query=диплом drive=D; "
    "'ищи файл на диске е' → drive=E. "

    "EN examples: "
    "'find my word documents' → category=document extension=docx; "
    "'search for music from this week' → category=music date_filter=week; "
    "'find large video files' → category=video size_filter=large; "
    "'find folder diploma' → category=folder query=diploma; "
    "'search for screenshots' → category=photo query=screenshot; "
    "'find photos' → category=photo; "
    "'search on drive D' → drive=D; "
    "'find diploma on drive D' → query=diploma drive=D."
)
PARAMETERS = {
    "query": {
        "type": "string",
        "description": "Имя файла/папки или часть имени",
    },
    "category": {
        "type": "string",
        "description": (
            "folder, document, photo, video, music, archive, code. "
            "Алиасы: папка/folder, ворд/word/документ/document, "
            "скриншот/screenshot→photo, фото/photo, видео/video, музыка/music, архив/archive, код/code"
        ),
        "enum": ["folder", "document", "photo", "video", "music", "archive", "code"],
    },
    "extension": {
        "type": "string",
        "description": "Расширение файла без точки: docx, pdf, xlsx, pptx, mp3, mp4, zip и т.д.",
    },
    "date_filter": {
        "type": "string",
        "description": "today, week, month, year",
        "enum": ["today", "week", "month", "year"],
    },
    "size_filter": {
        "type": "string",
        "description": "small (до 1МБ), medium (1-100МБ), large (свыше 100МБ)",
        "enum": ["small", "medium", "large"],
    },
    "drive": {
        "type": "string",
        "description": (
            "Буква диска для поиска (без двоеточия). Примеры: D, E, F. "
            "RU: 'ищи в диске д' → D; 'на диске е' → E. "
            "EN: 'on drive D' → D; 'search drive E' → E."
        ),
    },
}
REQUIRED = []

# ── Таблица алиасов естественного языка ───────────────────────────────────────
# Ключ — подстрока в нижнем регистре, значение — (category, extension_hint)

_ALIASES: list[tuple[str, str, str]] = [
    # (подстрока, category, ext_hint)
    # Папки
    ("папк",        "folder",   ""),
    ("каталог",     "folder",   ""),
    ("директори",   "folder",   ""),
    ("folder",      "folder",   ""),
    ("directory",   "folder",   ""),
    # Word
    ("ворд",        "document", "docx"),
    ("word",        "document", "docx"),
    # Excel
    ("эксел",       "document", "xlsx"),
    ("excel",       "document", "xlsx"),
    ("таблиц",      "document", "xlsx"),
    ("spreadsheet", "document", "xlsx"),
    # PowerPoint
    ("презентаци",  "document", "pptx"),
    ("powerpoint",  "document", "pptx"),
    # PDF
    ("пдф",         "document", "pdf"),
    # Документы (общее)
    ("документ",    "document", ""),
    ("document",    "document", ""),
    # Фото / Скриншоты
    ("фото",        "photo",    ""),
    ("картинк",     "photo",    ""),
    ("изображени",  "photo",    ""),
    ("скриншот",    "photo",    ""),
    ("скрин",       "photo",    ""),
    ("screenshot",  "photo",    ""),
    ("photo",       "photo",    ""),
    ("picture",     "photo",    ""),
    ("image",       "photo",    ""),
    # Видео
    ("видео",       "video",    ""),
    ("фильм",       "video",    ""),
    ("video",       "video",    ""),
    ("movie",       "video",    ""),
    ("film",        "video",    ""),
    # Музыка
    ("музык",       "music",    ""),
    ("песн",        "music",    ""),
    ("трек",        "music",    ""),
    ("music",       "music",    ""),
    ("song",        "music",    ""),
    ("audio",       "music",    ""),
    # Архивы
    ("архив",       "archive",  ""),
    ("archive",     "archive",  ""),
    # Код
    ("скрипт",      "code",     ""),
    ("script",      "code",     ""),
]


def _auto_detect(query: str, category: str, extension: str):
    """
    Если GPT не распознал category/extension — пытаемся определить
    из самого запроса по таблице алиасов.
    Возвращает (clean_query, category, extension).
    """
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
            # Убираем алиас из поискового запроса
            q_lower = q_lower.replace(alias, "").strip()

    clean_query = q_lower.strip(" -,.")
    return clean_query, detected_cat, detected_ext



_HERE      = pathlib.Path(__file__).parent
_STATE_KEY = "_jarvis_search_state"


def _get_state():
    if _STATE_KEY not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _STATE_KEY, _HERE / "_state.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_STATE_KEY] = mod
        spec.loader.exec_module(mod)
    return sys.modules[_STATE_KEY]


_ORDINALS_RU = ["Первый", "Второй", "Третий", "Четвёртый", "Пятый"]
_ORDINALS_EN = ["First",  "Second", "Third",  "Fourth",    "Fifth"]

_CAT_RU = {
    "folder":   "папок",
    "document": "документов",
    "photo":    "фотографий",
    "video":    "видео",
    "music":    "музыки",
    "archive":  "архивов",
    "code":     "файлов кода",
}

_CAT_EN = {
    "folder":   "folders",
    "document": "documents",
    "photo":    "photos",
    "video":    "videos",
    "music":    "music files",
    "archive":  "archives",
    "code":     "code files",
}


def handler(
    query:       str = "",
    category:    str = "",
    extension:   str = "",
    date_filter: str = "",
    size_filter: str = "",
    drive:       str = "",
) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    # Нормализация буквы диска: "д"→"D", "е"→"E" (RU раскладка)
    _ru_drive = {"а":"A","б":"B","в":"C","г":"D","д":"D","е":"E","ж":"F","з":"G","и":"H"}
    if drive:
        drive = _ru_drive.get(drive.lower(), drive).upper().strip(": \\")

    if not any([query, category, extension, date_filter, size_filter, drive]):
        if is_en:
            return "Please specify a filename, type (word, photo, video, music, folder), date, or drive."
        return (
            "Уточни поиск — назови имя файла, тип "
            "(ворд, фото, видео, музыка, папка), дату или диск."
        )

    from database.files.file_indexer import get_indexer
    from services.events import emit

    # Авто-определение категории из запроса если GPT не передал
    query, category, extension = _auto_detect(query, category, extension)

    indexer = get_indexer()

    results = indexer.search(
        query=query,
        category=category,
        extension=extension,
        date_filter=date_filter,
        size_filter=size_filter,
        drive=drive,
        limit=5,
        offset=0,
    )

    state = _get_state()
    state.set_results(
        results,
        query=query,
        offset=0,
        params={
            "query":       query,
            "category":    category,
            "extension":   extension,
            "date_filter": date_filter,
            "size_filter": size_filter,
            "drive":       drive,
        },
    )

    emit({
        "type":        "search_results",
        "results":     results,
        "query":       query,
        "category":    category,
        "extension":   extension,
        "date_filter": date_filter,
        "size_filter": size_filter,
        "drive":       drive,
        "total_shown": len(results),
    })

    ordinals = _ORDINALS_EN if is_en else _ORDINALS_RU
    cat_map  = _CAT_EN    if is_en else _CAT_RU

    if not results:
        hint = query or cat_map.get(category, "files" if is_en else "файлов")
        drive_hint = f" on drive {drive}" if (drive and is_en) else (f" на диске {drive}" if drive else "")
        if is_en:
            return f"Nothing found for '{hint}'{drive_hint}. Try rebuilding the index."
        return f"Ничего не нашёл по запросу «{hint}»{drive_hint}. Попробуй переиндексировать файлы."

    if len(results) == 1:
        if is_en:
            return f"Found: {results[0]['name']}. Say 'open' to open it."
        return f"Нашёл: {results[0]['name']}. Скажи «открой» чтобы открыть."

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