import sys
import importlib.util
import pathlib
import config

COMMAND_NAME = "search_files"
DESCRIPTION = (
    "Search for files and folders on the computer. "
    "/ Поиск файлов и папок на компьютере. "

    "RU triggers: найди, ищи, поищи, поиск, найти, где файл, открой файл, ищи файл, ищи папку. "
    "EN triggers: find, search for, look for, locate, where is my file, find folder. "

    # ── Категории ──────────────────────────────────────────────────────────
    "CATEGORY rules (set 'category' field): "
    "folder — ONLY when user explicitly says папку/папка/каталог/директорию/folder/directory. "
    "  Do NOT set category=folder when user says 'файл' (file) — 'файл' means any non-folder file. "
    "document — документ/ворд/word/pdf/таблица/excel/презентация/powerpoint. "
    "photo — фото/картинки/изображени/скриншот/скрин/screenshot/photo/picture/image. "
    "video — видео/фильм/video/movie/film. "
    "music — музыка/песни/треки/music/song/audio/mp3. "
    "archive — архив/archive/zip/rar. "
    "code — код/скрипт/code/script. "

    # ── Диск ───────────────────────────────────────────────────────────────
    "DRIVE filter — CRITICAL RULES: "
    "Set 'drive' to a single Latin letter (no colon, no slash). "
    "'в папке д', 'в папке D', 'на диске д', 'диск д', 'папка д' → drive=D (NOT category=folder!). "
    "'в папке с', 'диск с', 'на диске c' → drive=C. "
    "'в папке е', 'диск е' → drive=E. "
    "IMPORTANT: 'в папке X' where X is a drive letter means drive=X, NOT category=folder. "
    "Russian letter mappings: а→A, б→B, с→C, д→D, е→E, ф→F, г→G. "
    "EN: 'on drive D', 'in drive E', 'search drive C' → drive=D/E/C. "

    "DATE filter (date_filter): today, week, month, year. "
    "SIZE filter (size_filter): small (<1MB), medium (1-100MB), large (>100MB). "

    # ── Примеры RU ─────────────────────────────────────────────────────────
    "RU examples (by name): "
    "'найди папку диплом' → category=folder query=диплом; "
    "'ищи файл диплом' → query=диплом (no category!); "
    "'ищи папку' → category=folder query=''; "
    "'ищи в папке д' → drive=D (no category!); "
    "'ищи в папке с' → drive=C (no category!); "
    "'ищи в диске д' → drive=D; "
    "'найди диплом на диске д' → query=диплом drive=D; "
    "'найди ворд документы' → category=document extension=docx; "
    "'найди музыку за месяц' → category=music date_filter=month; "
    "'найди большие видео' → category=video size_filter=large. "

    "RU examples (by content — semantic=True): "
    "'найди файл где я писал про нейросети' → semantic=True query=нейросети; "
    "'найди документ о машинном обучении' → semantic=True query=машинное обучение; "
    "'где мой отчёт про продажи' → semantic=True query=продажи. "

    # ── Примеры EN ─────────────────────────────────────────────────────────
    "EN examples (by name): "
    "'find folder diploma' → category=folder query=diploma; "
    "'find file diploma' → query=diploma (no category!); "
    "'search in drive D' → drive=D (no category!); "
    "'search in folder D' → drive=D (NOT category=folder!); "
    "'find my word documents' → category=document extension=docx; "
    "'find large video files' → category=video size_filter=large. "

    "EN examples (by content — semantic=True): "
    "'find file about neural networks' → semantic=True query=neural networks; "
    "'find where I wrote about authentication' → semantic=True query=authentication; "
    "'find document about sales report' → semantic=True query=sales report."
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
    "semantic": {
        "type": "boolean",
        "description": (
            "True — поиск по СОДЕРЖИМОМУ файлов (смысл/тема). "
            "False (по умолчанию) — поиск по ИМЕНИ файла. "
            "Используй True когда пользователь ищет по смыслу, а не по названию. "
            "RU: 'найди файл где я писал про нейросети' → True; "
            "'найди документ о машинном обучении' → True; "
            "'найди диплом.docx' → False. "
            "EN: 'find file about neural networks' → True; "
            "'find where I wrote about X' → True; "
            "'find diploma.docx' → False."
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
    query:       str  = "",
    category:    str  = "",
    extension:   str  = "",
    date_filter: str  = "",
    size_filter: str  = "",
    drive:       str  = "",
    semantic:    bool = False,
) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    # Нормализация буквы диска — фонетическое соответствие RU→EN
    _ru_drive = {
        "а": "A", "б": "B", "с": "C", "д": "D",
        "е": "E", "ф": "F", "г": "G", "х": "H",
        "и": "I", "й": "J", "к": "K", "л": "L",
        "м": "M", "н": "N", "о": "O", "п": "P",
        "р": "R", "т": "T", "у": "U", "в": "V",
    }
    if drive:
        drive = _ru_drive.get(drive.lower(), drive).upper().strip(": \\")

    # Fallback: GPT иногда передаёт drive="папка д" или drive="диск д" вместо drive="D"
    if drive and len(drive) > 1:
        import re
        m = re.search(r'\b([a-zA-Zа-яА-Я])\b\s*$', drive)
        if m:
            letter = m.group(1)
            drive = _ru_drive.get(letter.lower(), letter).upper()
        else:
            drive = ""

    # Fallback: GPT передал drive в query — извлекаем "в папке Д/D" из запроса
    if not drive and query:
        import re
        m = re.search(
            r'(?:в\s+папк[еи]|на\s+диск[еу]|диск|in\s+(?:drive|folder))\s+([a-zA-Zа-яА-Я])\b',
            query, re.IGNORECASE
        )
        if m:
            letter = m.group(1)
            drive = _ru_drive.get(letter.lower(), letter).upper()
            # Убираем найденный паттерн из query
            query = re.sub(
                r'(?:в\s+папк[еи]|на\s+диск[еу]|диск|in\s+(?:drive|folder))\s+[a-zA-Zа-яА-Я]\b',
                '', query, flags=re.IGNORECASE
            ).strip(" ,.")

    if not any([query, category, extension, date_filter, size_filter, drive]):
        if is_en:
            return "Please specify a filename, topic, or type (word, photo, video, music, folder)."
        return "Уточни поиск — назови имя файла, тему или тип (ворд, фото, видео, музыка, папка)."

    from database.files.file_indexer import get_indexer
    from services.events import emit

    # Если GPT поставил category=folder, но пользователь говорил про файл — сброс
    _file_words = {"файл", "файлы", "file", "files"}
    if category == "folder" and any(w in query.lower().split() for w in _file_words):
        category = ""

    # Авто-определение категории из запроса если GPT не передал
    query, category, extension = _auto_detect(query, category, extension)

    results: list[dict] = []

    # ── Семантический поиск по содержимому ───────────────────────────────────
    if semantic and query:
        try:
            from database.files.semantic_search import get_semantic_indexer
            api_key = getattr(config, "OPENAI_API_KEY", "")
            sem_results = get_semantic_indexer().search(
                query=query,
                api_key=api_key,
                limit=5,
                category=category,
            )
            results = sem_results
        except Exception as e:
            print(f"  [semantic] Ошибка поиска: {e}")

    # ── Обычный поиск по имени (всегда, дополняет семантику без дублей) ──────
    seen_paths = {r["path"] for r in results}
    indexer    = get_indexer()
    fuzzy_results = indexer.search(
        query=query,
        category=category,
        extension=extension,
        date_filter=date_filter,
        size_filter=size_filter,
        drive=drive,
        limit=5,
        offset=0,
    )
    for r in fuzzy_results:
        if r["path"] not in seen_paths:
            results.append(r)
            seen_paths.add(r["path"])

    results = results[:5]

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
            "semantic":    semantic,
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
        "semantic":    semantic,
        "total_shown": len(results),
    })

    ordinals = _ORDINALS_EN if is_en else _ORDINALS_RU
    cat_map  = _CAT_EN    if is_en else _CAT_RU

    if not results:
        hint       = query or cat_map.get(category, "files" if is_en else "файлов")
        drive_hint = f" on drive {drive}" if (drive and is_en) else (f" на диске {drive}" if drive else "")
        if semantic:
            if is_en:
                return f"Nothing found by content for '{hint}'{drive_hint}. The file may not be indexed yet — try rebuilding the index."
            return f"Ничего не нашёл по содержимому для «{hint}»{drive_hint}. Возможно файл ещё не проиндексирован — попробуй переиндексировать."
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