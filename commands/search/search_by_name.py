import importlib.util
import pathlib
import config

# Загружаем _helpers.py напрямую по пути — избегаем дедлока с commands/__init__.py
_h_spec = importlib.util.spec_from_file_location(
    "_search_helpers", pathlib.Path(__file__).parent / "_helpers.py"
)
_h = importlib.util.module_from_spec(_h_spec)
_h_spec.loader.exec_module(_h)
auto_detect = _h.auto_detect
normalize_drive = _h.normalize_drive
get_state = _h.get_state
format_results = _h.format_results
CAT_RU = _h.CAT_RU
CAT_EN = _h.CAT_EN

COMMAND_NAME = "search_by_name"
DESCRIPTION = (
    "Search for files and folders BY NAME on the computer. "
    "/ Поиск файлов и папок по ИМЕНИ на компьютере. "

    "Use this command when the user knows (part of) the filename or wants to filter by type/size/date. "
    "Do NOT use this for content search ('найди где я писал про...', 'find where I wrote about...'). "

    "RU triggers: найди, ищи, поищи, найти, где файл, открой файл, ищи файл, ищи папку. "
    "EN triggers: find, search for, look for, locate, where is my file, find folder. "

    "CATEGORY rules: "
    "folder — папку/папка/каталог/директорию/folder/directory. "
    "document — документ/ворд/word/pdf/таблица/excel/презентация/powerpoint. "
    "photo — фото/картинки/изображени/скриншот/скрин/screenshot/photo/picture/image. "
    "video — видео/фильм/video/movie/film. "
    "music — музыка/песни/треки/music/song/audio/mp3. "
    "archive — архив/archive/zip/rar. "
    "code — код/скрипт/code/script. "

    "DRIVE filter — set 'drive' to a single Latin letter (no colon). "
    "'в папке д', 'диск д' → drive=D. 'в папке с' → drive=C. "
    "Russian letter mappings: а→A, б→B, с→C, д→D, е→E, ф→F, г→G. "

    "DATE filter: today, week, month, year. "
    "SIZE filter: small (<1MB), medium (1-100MB), large (>100MB). "

    "RU examples: "
    "'найди папку диплом' → category=folder query=диплом; "
    "'ищи файл диплом' → query=диплом; "
    "'найди диплом на диске д' → query=диплом drive=D; "
    "'найди ворд документы' → category=document extension=docx; "
    "'найди музыку за месяц' → category=music date_filter=month; "
    "'найди большие видео' → category=video size_filter=large. "

    "EN examples: "
    "'find folder diploma' → category=folder query=diploma; "
    "'find large video files' → category=video size_filter=large; "
    "'search drive D' → drive=D."
)
PARAMETERS = {
    "query": {
        "type": "string",
        "description": "Имя файла/папки или часть имени / File or folder name (partial ok)",
    },
    "category": {
        "type": "string",
        "description": "folder, document, photo, video, music, archive, code",
        "enum": ["folder", "document", "photo", "video", "music", "archive", "code"],
    },
    "extension": {
        "type": "string",
        "description": "File extension without dot: docx, pdf, xlsx, mp3, mp4, zip, etc.",
    },
    "date_filter": {
        "type": "string",
        "description": "today, week, month, year",
        "enum": ["today", "week", "month", "year"],
    },
    "size_filter": {
        "type": "string",
        "description": "small (<1MB), medium (1-100MB), large (>100MB)",
        "enum": ["small", "medium", "large"],
    },
    "drive": {
        "type": "string",
        "description": (
            "Drive letter to search (no colon). "
            "RU: 'диск д' → D, 'диск е' → E. EN: 'drive D' → D."
        ),
    },
}
REQUIRED = []


def handler(
    query:       str = "",
    category:    str = "",
    extension:   str = "",
    date_filter: str = "",
    size_filter: str = "",
    drive:       str = "",
) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    drive, query = normalize_drive(drive, query)

    if not any([query, category, extension, date_filter, size_filter, drive]):
        return (
            "Please specify a filename or type (photo, video, music, folder)."
            if is_en else
            "Уточни поиск — назови имя файла или тип (ворд, фото, видео, папка)."
        )

    from database.files.file_indexer import get_indexer
    from services.events import emit

    # ИИ иногда ставит category=folder когда пользователь говорит "файл"
    _file_words = {"файл", "файлы", "file", "files"}
    if category == "folder" and any(w in query.lower().split() for w in _file_words):
        category = ""

    query, category, extension = auto_detect(query, category, extension)

    results = get_indexer().search(
        query=query,
        category=category,
        extension=extension,
        date_filter=date_filter,
        size_filter=size_filter,
        drive=drive,
        limit=5,
        offset=0,
    )

    state = get_state()
    state.set_results(
        results,
        query=query,
        offset=0,
        params={
            "query": query, "category": category, "extension": extension,
            "date_filter": date_filter, "size_filter": size_filter,
            "drive": drive, "semantic": False,
        },
    )

    emit({
        "type": "search_results",
        "results": results,
        "query": query, "category": category, "extension": extension,
        "date_filter": date_filter, "size_filter": size_filter,
        "drive": drive, "semantic": False,
        "total_shown": len(results),
    })

    if not results:
        hint = query or CAT_EN.get(category, "files") if is_en else CAT_RU.get(category, "файлов")
        drive_hint = (f" on drive {drive}" if drive and is_en else f" на диске {drive}" if drive else "")
        return (
            f"Nothing found for '{hint}'{drive_hint}. Try rebuilding the index."
            if is_en else
            f"Ничего не нашёл по запросу «{hint}»{drive_hint}. Попробуй переиндексировать файлы."
        )

    return format_results(results, is_en)
