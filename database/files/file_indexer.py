"""
SQLite индекс файлов пользователя.
Сканирует Desktop, Documents, Downloads, Music, Pictures, Videos.
"""

import os
import sqlite3
import threading
import time
import pathlib
import datetime
from difflib import SequenceMatcher

# ── Заимствованные слова RU → EN ──────────────────────────────────────────────
# Транслитерация "скриншот" → "skrinshot", но реальный файл "screenshot".
# Этот словарь даёт точный EN-оригинал для поиска.
_LOANWORDS: dict[str, str] = {
    # Форматы / инструменты
    "скриншот":   "screenshot",
    "скриншоты":  "screenshot",
    "ворд":       "word",
    "эксель":     "excel",
    "экзель":     "excel",
    "питон":      "python",
    "джанго":     "django",
    "реакт":      "react",
    "ноджс":      "nodejs",
    "пдф":        "pdf",
    "зип":        "zip",
    "рар":        "rar",
    "майкрософт": "microsoft",
    "гитхаб":     "github",
    # Медиа / общие слова
    "фото":       "photo",
    "клипы":      "clips",
    "клип":       "clip",
    # Браузеры
    "хром":       "chrome",
    "хромиум":    "chromium",
    "файрфокс":   "firefox",
    "опера":      "opera",
    "яндекс":     "yandex",
    # Мессенджеры / соцсети
    "телеграм":   "telegram",
    "телега":     "telegram",
    "ватсап":     "whatsapp",
    "вотсап":     "whatsapp",
    "дискорд":    "discord",
    "скайп":      "skype",
    "зум":        "zoom",
    "вайбер":     "viber",
    # Офис / утилиты
    "фотошоп":    "photoshop",
    "иллюстратор":"illustrator",
    "блокнот":    "notepad",
    "пейнт":      "paint",
    "проводник":  "explorer",
    "калькулятор":"calculator",
    "ноутпад":    "notepad",
    # Игры / платформы
    "стим":       "steam",
    "майнкрафт":  "minecraft",
    # Разработка
    "докер":      "docker",
    "гит":        "git",
    "линукс":     "linux",
    "убунту":     "ubuntu",
    "андроид":    "android",
}
# "скрин" убран — он подстрока "скриншот" и вызывал мусор типа "screenshotшот"

# Обратный словарь EN→RU для кросс-языкового поиска
_LOANWORDS_EN: dict[str, str] = {
    # Форматы / инструменты
    "screenshot":   "скриншот",
    "word":         "ворд",
    "excel":        "эксель",
    "python":       "питон",
    "django":       "джанго",
    "react":        "реакт",
    "nodejs":       "ноджс",
    "pdf":          "пдф",
    "zip":          "зип",
    "rar":          "рар",
    "microsoft":    "майкрософт",
    "github":       "гитхаб",
    # Медиа / общие слова
    "photo":        "фото",
    "clip":         "клип",
    "clips":        "клипы",
    # Браузеры
    "chrome":       "хром",
    "chromium":     "хромиум",
    "firefox":      "файрфокс",
    "opera":        "опера",
    "yandex":       "яндекс",
    # Мессенджеры / соцсети
    "telegram":     "телеграм",
    "whatsapp":     "ватсап",
    "discord":      "дискорд",
    "skype":        "скайп",
    "zoom":         "зум",
    "viber":        "вайбер",
    # Офис / утилиты
    "photoshop":    "фотошоп",
    "illustrator":  "иллюстратор",
    "notepad":      "блокнот",
    "paint":        "пейнт",
    "explorer":     "проводник",
    "calculator":   "калькулятор",
    # Игры / платформы
    "steam":        "стим",
    "minecraft":    "майнкрафт",
    # Разработка
    "docker":       "докер",
    "git":          "гит",
    "linux":        "линукс",
    "ubuntu":       "убунту",
    "android":      "андроид",
}

# ── Транслитерация RU ↔ EN ────────────────────────────────────────────────────

_RU_TO_EN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo',
    'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch',
    'ъ':'', 'ы':'y','ь':'', 'э':'e','ю':'yu','я':'ya',
}


_EN_TO_RU = [
    ('shch','щ'),('sch','щ'),('zh','ж'),('kh','х'),('ts','ц'),
    ('ch','ч'),('sh','ш'),('yu','ю'),('ya','я'),('yo','ё'),
    ('a','а'),('b','б'),('v','в'),('g','г'),('d','д'),('e','е'),
    ('z','з'),('i','и'),('y','й'),('k','к'),('l','л'),('m','м'),
    ('n','н'),('o','о'),('p','п'),('r','р'),('s','с'),('t','т'),
    ('u','у'),('f','ф'),('h','х'),
]


def _to_latin(text: str) -> str:
    return ''.join(_RU_TO_EN.get(c, c) for c in text.lower())


def _to_cyrillic(text: str) -> str:
    result = text.lower()
    for lat, cyr in _EN_TO_RU:
        result = result.replace(lat, cyr)
    return result


_VOWELS_CYR = frozenset('аеёиоуыэюя')
_VOWELS_LAT = frozenset('aeiou')


def _query_variants(query: str) -> list[str]:
    """Оригинал + транслитерация (RU↔EN) + заимствованные слова + стем.

    Стем нужен для кросс-языкового поиска: 'diploma' → 'диплома' → 'диплом',
    чтобы LIKE 'диплом%' нашёл файл 'Диплом.docx' без fuzzy.
    Заимствованные слова: 'скриншот' → 'screenshot' (транслитерация не совпадает).
    """
    q_stripped = query.lower().strip()
    if not query or (len(q_stripped) <= 3
                     and q_stripped not in _LOANWORDS
                     and q_stripped not in _LOANWORDS_EN):
        return [query]
    q = q_stripped
    has_cyr = any('Ѐ' <= c <= 'ӿ' for c in q)
    has_lat = any('a' <= c <= 'z' for c in q)
    variants = [q]

    if has_cyr and not has_lat:
        alt = _to_latin(q)
        if alt and alt != q:
            variants.append(alt)
            if len(alt) > 4 and alt[-1] in _VOWELS_LAT:
                variants.append(alt[:-1])
    elif has_lat and not has_cyr:
        alt = _to_cyrillic(q)
        if alt and alt != q:
            variants.append(alt)
            if len(alt) > 4 and alt[-1] in _VOWELS_CYR:
                variants.append(alt[:-1])

    # RU→EN заимствования: "скриншот" → "screenshot"
    # Применяем только самое длинное совпадение (сортировка по убыванию длины)
    # чтобы "скриншот" не давал ещё и мусор от "скрин"
    _applied: set[str] = set()
    for ru_word, en_word in sorted(_LOANWORDS.items(), key=lambda x: -len(x[0])):
        if ru_word in q and not any(ru_word in a for a in _applied):
            loan = q.replace(ru_word, en_word).strip()
            if loan and loan not in variants:
                variants.append(loan)
            _applied.add(ru_word)

    # EN→RU заимствования: "screenshot" → "скриншот"
    if has_lat and not has_cyr:
        for en_word, ru_word in _LOANWORDS_EN.items():
            if en_word in q:
                loan = q.replace(en_word, ru_word).strip()
                if loan and loan not in variants:
                    variants.append(loan)

    return list(dict.fromkeys(variants))


def _build_search_text(name: str) -> str:
    """Строит cross-language строку для имени файла.

    Разбивает имя на слова по разделителям, добавляет оригинал +
    латинский транслит кириллицы + кириллический транслит латиницы.

    'report_final_2024.pdf' → 'report final 2024 pdf репорт финал'
    'Диплом_финал.docx'    → 'диплом финал docx diplom final'
    """
    lower = name.lower()
    words: list[str] = []
    current: list[str] = []
    for ch in lower:
        if ch in '_-. \t':
            if current:
                words.append(''.join(current))
                current = []
        else:
            current.append(ch)
    if current:
        words.append(''.join(current))

    parts: list[str] = []
    seen_w: set[str] = set()

    def _add(s: str) -> None:
        if s and s not in seen_w:
            parts.append(s)
            seen_w.add(s)

    for word in words:
        _add(word)
        if len(word) <= 3:
            continue
        has_cyr = any('Ѐ' <= c <= 'ӿ' for c in word)
        has_lat = any('a' <= c <= 'z' for c in word)
        if has_cyr:
            lat = _to_latin(word)
            if not any('Ѐ' <= c <= 'ӿ' for c in lat):
                _add(lat)
            # RU→EN заимствование для name_search
            if word in _LOANWORDS:
                _add(_LOANWORDS[word])
        if has_lat:
            cyr = _to_cyrillic(word)
            if not any('a' <= c <= 'z' for c in cyr):
                _add(cyr)
            # EN→RU заимствование для name_search
            if word in _LOANWORDS_EN:
                _add(_LOANWORDS_EN[word])

    return ' '.join(parts)


DB_PATH = pathlib.Path(__file__).parent / "files.db"

HOME = pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home())))

# ── Приоритеты сканирования ────────────────────────────────────────────────────
# Фаза 1: самые важные папки — результаты через ~5-10 сек
def _win_special_folders() -> list[pathlib.Path]:
    """
    Читает реальные пути Desktop / Documents / Downloads / Pictures /
    Music / Videos из реестра Windows.
    Работает для любого пользователя и любого диска/языка.
    """
    _SHELL_FOLDERS = {
        "Desktop", "Personal", "{374DE290-123F-4565-9164-39C4925E467B}",
        "My Pictures", "My Music", "My Video",
    }
    result = []
    try:
        import winreg
        for hive in (
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, hive)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    i += 1
                    if name in _SHELL_FOLDERS and isinstance(value, str):
                        # Раскрываем переменные окружения (%USERPROFILE% и т.д.)
                        expanded = os.path.expandvars(value)
                        p = pathlib.Path(expanded)
                        if p.exists() and p not in result:
                            result.append(p)
                except OSError:
                    break
            winreg.CloseKey(key)
    except Exception:
        pass
    return result


PRIORITY_DIRS = list(dict.fromkeys(filter(
    lambda p: p.exists(),
    [
        HOME / "Desktop",
        HOME / "Downloads",
        HOME / "Documents",
        HOME / "OneDrive" / "Desktop",
        HOME / "OneDrive" / "Рабочий стол",
        HOME / "OneDrive" / "Documents",
        HOME / "OneDrive" / "Документы",
        *_win_special_folders(),   # реальные пути из реестра Windows
    ]
)))

# Фаза 2: медиа и вся папка пользователя — через ~30-60 сек
EXTENDED_DIRS = [
    HOME / "Music",
    HOME / "Pictures",
    HOME / "Videos",
    HOME,   # вся папка пользователя (AppData исключается через SKIP_DIR_PARTS)
]


def _get_extra_drives() -> list[pathlib.Path]:
    """Фаза 3: все диски кроме C:\\ — D:\\, E:\\ и т.д."""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        if letter.upper() == "C":
            continue
        drive = pathlib.Path(f"{letter}:\\")
        if drive.exists():
            drives.append(drive)
    return drives

# Папка самого проекта Jarvis — исключаем чтобы не индексировать модели и кэш
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent.parent).lower()

SKIP_DIR_PARTS = {
    # Системные
    "windows", "system32", "syswow64", "winsxs",
    "program files", "program files (x86)",
    "$recycle.bin", "system volume information",
    # AppData — общий мусор
    "appdata\\local\\temp",
    "appdata\\roaming\\microsoft", "appdata\\local\\microsoft",
    "appdata\\local\\google",    "appdata\\local\\packages",
    # SDK и среды разработки
    "appdata\\local\\android",   # Android SDK (сотни тысяч файлов)
    "appdata\\local\\jetbrains", # JetBrains IDE кэши
    "appdata\\local\\programs",  # установленные программы
    "appdata\\local\\npm-cache", # npm кэш
    "appdata\\roaming\\npm",
    # Приложения с логами/кэшем
    "appdata\\local\\ciscospark",
    "appdata\\local\\cisco",
    "appdata\\local\\slack",
    "appdata\\local\\discord",
    "appdata\\roaming\\discord",
    "appdata\\local\\com.tauri",   # Tauri EBWebView
    "appdata\\local\\tauri",
    "appdata\\local\\electron",
    "appdata\\roaming\\code",      # VS Code extensions
    "appdata\\local\\webstorm",
    "ebwebview",                   # Chromium WebView кэши
    # Разработка
    "node_modules", ".git", "__pycache__",
    "venv", ".venv", "site-packages",
    ".idea", ".vscode",
    # Папки с большими бинарниками
    "migrations",
}


def _should_skip(path: pathlib.Path) -> bool:
    p_lower = str(path).lower()
    # Исключаем папку самого проекта
    if p_lower.startswith(_PROJECT_ROOT):
        return True
    return any(skip in p_lower for skip in SKIP_DIR_PARTS)

CATEGORIES = {
    "document": {"pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx",
                 "odt", "ods", "odp", "rtf", "csv", "epub", "djvu"},
    "photo":    {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif",
                 "heic", "raw", "cr2", "nef", "arw", "psd"},
    "video":    {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v",
                 "3gp", "mpeg", "mpg", "ts", "vob"},
    "music":    {"mp3", "flac", "wav", "aac", "ogg", "m4a", "wma", "opus", "aiff"},
    "archive":  {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso", "cab"},
    "code":     {"py", "js", "ts", "html", "css", "json", "xml", "yaml", "yml",
                 "java", "cpp", "c", "h", "cs", "php", "rb", "go", "rs", "sh",
                 "bat", "sql", "md"},
}


# Атрибуты Windows для cloud-only файлов OneDrive (не скачаны на диск)
_CLOUD_ATTRIBUTES = (
    0x400000,  # FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    0x040000,  # FILE_ATTRIBUTE_RECALL_ON_OPEN
)


def _is_cloud_only(stat_result) -> bool:
    """Возвращает True если файл хранится только в облаке (не скачан)."""
    attrs = getattr(stat_result, "st_file_attributes", 0)
    return any(attrs & flag for flag in _CLOUD_ATTRIBUTES)


def _get_category(ext: str) -> str:
    e = ext.lower().lstrip(".")
    for cat, exts in CATEGORIES.items():
        if e in exts:
            return cat
    return "other"



def _human_size(b: int) -> str:
    if b < 1024:        return f"{b} Б"
    if b < 1024 ** 2:   return f"{b // 1024} КБ"
    if b < 1024 ** 3:   return f"{b // 1024 ** 2} МБ"
    return f"{b / 1024 ** 3:.1f} ГБ"


class FileIndexer:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._needs_rebuild = False
        self._init_db()

        # Прогресс индексации
        self._progress: dict = {
            "is_indexing": False,
            "scanned":     0,
            "total":       0,
            "percent":     0,
            "started_at":  None,
        }

        self._observer = None
        threading.Thread(target=self._auto_build_and_watch, daemon=True).start()

    # ── Инициализация БД ──────────────────────────────────────────────────────

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                name_lower  TEXT NOT NULL,
                path        TEXT NOT NULL UNIQUE,
                extension   TEXT NOT NULL,
                category    TEXT NOT NULL,
                size_bytes  INTEGER NOT NULL,
                modified_at REAL NOT NULL,
                indexed_at  REAL NOT NULL,
                name_search TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_name     ON files(name_lower);
            CREATE INDEX IF NOT EXISTS idx_cat      ON files(category);
            CREATE INDEX IF NOT EXISTS idx_modified ON files(modified_at);
            CREATE INDEX IF NOT EXISTS idx_size     ON files(size_bytes);
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self._conn.commit()
        # Миграция: добавляем name_search в существующую БД если его нет
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(files)").fetchall()}
        if 'name_search' not in cols:
            self._conn.execute(
                "ALTER TABLE files ADD COLUMN name_search TEXT NOT NULL DEFAULT ''"
            )
            self._conn.commit()
            self._needs_rebuild = True

    def _auto_build_and_watch(self):
        """Запускается в фоне при старте: rebuild если нужно, потом watchdog."""
        if self._needs_rebuild:
            self.build_index()
            return
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key='last_build'"
            ).fetchone()
        if row is None or (time.time() - float(row["value"]) > 86400):
            self.build_index()   # _start_watcher вызывается внутри build_index
        else:
            self._start_watcher()  # индекс свежий — только запускаем watcher
            # Удаляем записи файлов, которые исчезли пока сервер был выключен
            threading.Thread(target=self._cleanup_stale, daemon=True).start()

    def _cleanup_stale(self):
        """Удаляет из индекса записи о файлах/папках, которых больше нет на диске.
        Работает порциями по 1000, чтобы не тормозить систему.
        """
        BATCH = 1000
        offset = 0
        total_removed = 0
        while True:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT path FROM files LIMIT ? OFFSET ?", (BATCH, offset)
                ).fetchall()
            if not rows:
                break
            dead = [r[0] for r in rows if not os.path.exists(r[0])]
            if dead:
                self._remove_dead(dead)
                total_removed += len(dead)
            offset += BATCH - len(dead)   # сдвигаемся с учётом удалённых
            time.sleep(0.05)              # не нагружаем диск
        if total_removed:
            try:
                print(f"    [cleanup] Удалено устаревших записей: {total_removed}")
            except Exception:
                pass

    # ── Построение индекса (3 фазы) ────────────────────────────────────────────

    def build_index(self) -> int:
        from services.events import emit

        started = time.time()
        self._progress = {
            "is_indexing": True,
            "phase":       1,
            "phase_label": "Приоритетные папки",
            "scanned":     0,
            "total":       0,
            "percent":     0,
            "started_at":  started,
        }
        emit({"type": "index_progress", **self._progress})

        # Первый запуск — очищаем старые данные
        with self._lock:
            self._conn.execute("DELETE FROM files")
            self._conn.commit()

        total_indexed = 0
        # Единый сет на весь build — дедупликация между фазами без запросов к БД.
        # DB уже очищена выше, поэтому сет начинается пустым.
        seen_in_build: set[str] = set()

        phases = [
            (1, "Приоритетные папки",   [d for d in PRIORITY_DIRS if d.exists()]),
            (2, "Медиа и пользователь", [d for d in EXTENDED_DIRS if d.exists()]),
            (3, "Остальные диски",      _get_extra_drives()),
        ]

        for phase_num, phase_label, dirs in phases:
            if not dirs:
                continue

            # Быстрый подсчёт файлов в фазе
            phase_total = 0
            for d in dirs:
                for _, _, files in os.walk(str(d)):
                    phase_total += len(files)

            scanned = 0
            batch: list[tuple] = []
            now = time.time()

            for scan_dir in dirs:
                for root, dirs_list, files in os.walk(str(scan_dir), followlinks=False):
                    root_path = pathlib.Path(root)
                    dirs_list[:] = [
                        d for d in dirs_list
                        if not d.startswith(".") and not _should_skip(root_path / d)
                    ]
                    # Индексируем папки текущего уровня
                    for dname in dirs_list:
                        dpath     = root_path / dname
                        dpath_str = str(dpath)
                        if dpath_str in seen_in_build:
                            continue
                        try:
                            stat = dpath.stat()
                            batch.append((
                                dname, dname.lower(), dpath_str,
                                "", "folder", 0, stat.st_mtime, now,
                                _build_search_text(dname),
                            ))
                            seen_in_build.add(dpath_str)
                        except (OSError, PermissionError):
                            pass

                    # Индексируем файлы
                    for fname in files:
                        fpath = root_path / fname
                        fpath_str = str(fpath)

                        if fpath_str in seen_in_build:
                            scanned += 1
                            continue

                        try:
                            stat = fpath.stat()
                            if _is_cloud_only(stat):   # OneDrive — не скачан
                                scanned += 1
                                continue
                            ext  = fpath.suffix
                            batch.append((
                                fname,
                                fname.lower(),
                                fpath_str,
                                ext.lower().lstrip("."),
                                _get_category(ext),
                                stat.st_size,
                                stat.st_mtime,
                                now,
                                _build_search_text(fname),
                            ))
                            seen_in_build.add(fpath_str)
                        except (OSError, PermissionError):
                            pass
                        scanned += 1

                        # Пишем батч в БД каждые 500 файлов — результаты доступны сразу
                        if len(batch) >= 500:
                            self._flush(batch)
                            total_indexed += len(batch)
                            batch.clear()

                        # Прогресс каждые 300 файлов
                        if scanned % 300 == 0:
                            pct = int(scanned * 100 / phase_total) if phase_total > 0 else 0
                            self._progress = {
                                "is_indexing": True,
                                "phase":       phase_num,
                                "phase_label": phase_label,
                                "scanned":     total_indexed + len(batch),
                                "total":       phase_total,
                                "percent":     min(99, pct),
                                "started_at":  started,
                            }
                            emit({"type": "index_progress", **self._progress})

            # Дописываем остаток батча
            if batch:
                self._flush(batch)
                total_indexed += len(batch)
                batch.clear()

            emit({
                "type": "index_progress",
                "is_indexing": True,
                "phase":       phase_num,
                "phase_label": f"{phase_label} — готово",
                "scanned":     total_indexed,
                "total":       total_indexed,
                "percent":     min(99, phase_num * 33),
                "started_at":  started,
            })

        # Завершение
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('last_build', ?)",
                (str(time.time()),),
            )
            self._conn.commit()

        self._progress = {
            "is_indexing": False,
            "phase":       3,
            "phase_label": "Готово",
            "scanned":     total_indexed,
            "total":       total_indexed,
            "percent":     100,
            "started_at":  None,
        }
        emit({"type": "index_progress", **self._progress})
        self._start_watcher()

        # Запускаем семантическую индексацию в фоне после завершения файлового индекса
        def _start_semantic():
            try:
                import config
                from database.files.semantic_search import get_semantic_indexer, ALL_SUPPORTED
                api_key = getattr(config, "OPENAI_API_KEY", "")
                if not api_key:
                    return
                # Берём все документы из files.db с нужными расширениями
                with self._lock:
                    rows = self._conn.execute(
                        "SELECT path FROM files WHERE extension IN ({})".format(
                            ",".join("?" * len(ALL_SUPPORTED))
                        ),
                        list(ALL_SUPPORTED),
                    ).fetchall()
                paths = [r["path"] for r in rows]
                if paths:
                    try:
                        print(f"    [semantic] Запуск индексации {len(paths)} документов...")
                    except Exception:
                        pass
                    get_semantic_indexer().build_index(paths, api_key)
            except Exception as e:
                try:
                    print(f"    [semantic] Ошибка запуска: {e}")
                except Exception:
                    pass

        threading.Thread(target=_start_semantic, daemon=True, name="semantic-build").start()
        return total_indexed

    # ── Инкрементальные обновления (watchdog) ─────────────────────────────────

    def _index_path(self, path: str):
        """Добавить или обновить файл или папку в индексе."""
        fpath = pathlib.Path(path)
        if _should_skip(fpath.parent):
            return
        try:
            stat = fpath.stat()
            is_dir = fpath.is_dir()
            ext    = "" if is_dir else fpath.suffix
            cat    = "folder" if is_dir else _get_category(ext)
            size   = 0 if is_dir else stat.st_size
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO files "
                    "(name, name_lower, path, extension, category, size_bytes, modified_at, indexed_at, name_search) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fpath.name, fpath.name.lower(), str(fpath),
                     ext.lower().lstrip("."), cat, size, stat.st_mtime, time.time(),
                     _build_search_text(fpath.name)),
                )
                self._conn.commit()
            # Ставим в очередь семантической индексации (только файлы, не папки)
            if not is_dir:
                try:
                    from database.files.semantic_search import get_semantic_indexer
                    get_semantic_indexer().enqueue(str(fpath))
                except Exception:
                    pass
        except (OSError, PermissionError):
            pass

    def _index_dir(self, path: str):
        """Рекурсивно переиндексировать всё содержимое папки (после переноса)."""
        fpath = pathlib.Path(path)
        if not fpath.is_dir() or _should_skip(fpath):
            return
        batch: list[tuple] = []
        now = time.time()
        for root, dirs_list, files in os.walk(str(fpath), followlinks=False):
            root_path = pathlib.Path(root)
            dirs_list[:] = [
                d for d in dirs_list
                if not d.startswith(".") and not _should_skip(root_path / d)
            ]
            for dname in dirs_list:
                dpath = root_path / dname
                try:
                    stat = dpath.stat()
                    batch.append((
                        dname, dname.lower(), str(dpath),
                        "", "folder", 0, stat.st_mtime, now,
                        _build_search_text(dname),
                    ))
                except (OSError, PermissionError):
                    pass
            for fname in files:
                fpath2 = root_path / fname
                try:
                    stat = fpath2.stat()
                    if _is_cloud_only(stat):
                        continue
                    ext = fpath2.suffix
                    batch.append((
                        fname, fname.lower(), str(fpath2),
                        ext.lower().lstrip("."), _get_category(ext),
                        stat.st_size, stat.st_mtime, now,
                        _build_search_text(fname),
                    ))
                except (OSError, PermissionError):
                    pass
            if len(batch) >= 500:
                self._flush(batch)
                batch.clear()
        if batch:
            self._flush(batch)

    # обратная совместимость
    def _index_file(self, path: str):
        self._index_path(path)

    def _remove_file(self, path: str):
        """Удалить файл или папку (со всем содержимым) из индекса."""
        prefix = path.rstrip("/\\") + os.sep
        with self._lock:
            self._conn.execute(
                "DELETE FROM files WHERE path = ? OR path LIKE ?",
                (path, prefix + "%"),
            )
            self._conn.commit()
        try:
            from database.files.semantic_search import get_semantic_indexer
            get_semantic_indexer().remove_path(path)
        except Exception:
            pass

    def _start_watcher(self):
        """Запустить watchdog — следить за изменениями файловой системы."""
        if self._observer is not None:
            return  # уже запущен

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            indexer = self

            # Дебаунсинг: накапливаем события 1 секунду, потом пишем в БД одним батчем
            _pending: dict[str, str] = {}   # path → "add" | "remove"
            _debounce_lock = threading.Lock()
            _debounce_timer: list = [None]

            def _flush_pending():
                with _debounce_lock:
                    batch = dict(_pending)
                    _pending.clear()
                for path, action in batch.items():
                    if action == "add":
                        indexer._index_path(path)
                    elif action == "reindex_dir":
                        indexer._index_dir(path)
                    else:
                        indexer._remove_file(path)

            def _schedule(path: str, action: str):
                with _debounce_lock:
                    _pending[path] = action
                    if _debounce_timer[0] is not None:
                        _debounce_timer[0].cancel()
                    t = threading.Timer(1.0, _flush_pending)
                    t.daemon = True
                    t.start()
                    _debounce_timer[0] = t

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if event.is_directory:
                        _schedule(event.src_path, "reindex_dir")
                    else:
                        _schedule(event.src_path, "add")

                def on_deleted(self, event):
                    _schedule(event.src_path, "remove")

                def on_moved(self, event):
                    _schedule(event.src_path, "remove")
                    if event.is_directory:
                        _schedule(event.dest_path, "reindex_dir")
                    else:
                        _schedule(event.dest_path, "add")

                def on_modified(self, event):
                    if not event.is_directory:
                        _schedule(event.src_path, "add")

            observer = Observer()
            handler  = _Handler()
            watched  = set()

            for d in PRIORITY_DIRS + EXTENDED_DIRS + _get_extra_drives():
                if d.exists() and str(d) not in watched:
                    observer.schedule(handler, str(d), recursive=True)
                    watched.add(str(d))
                    try:
                        print(f"    [watcher] Слежу: {d}")
                    except Exception:
                        pass

            observer.daemon = True
            observer.start()
            self._observer = observer
            try:
                print(f"    [watcher] Запущен. Папок под наблюдением: {len(watched)}")
            except Exception:
                pass

        except ImportError:
            try:
                print("    [watcher] watchdog не установлен (pip install watchdog)")
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"    [watcher] Ошибка запуска: {e}")
            except Exception:
                pass

    def _flush(self, batch: list[tuple]):
        """Записывает батч файлов в БД — не блокирует поиск надолго."""
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO files "
                "(name, name_lower, path, extension, category, size_bytes, modified_at, indexed_at, name_search) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            self._conn.commit()

    def get_progress(self) -> dict:
        return dict(self._progress)

    # ── Поиск ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query:       str = "",
        category:    str = "",
        extension:   str = "",
        date_filter: str = "",
        size_filter: str = "",
        drive:       str = "",
        limit:       int = 5,
        offset:      int = 0,
    ) -> list[dict]:
        # Ищем по оригинальному запросу + транслитерированному варианту + заимствованным словам
        variants = _query_variants(query)
        if len(variants) > 1:
            seen, merged = set(), []
            for v in variants:
                for r in self._search_one(
                    query=v, category=category, extension=extension,
                    date_filter=date_filter, size_filter=size_filter,
                    drive=drive, limit=limit, offset=offset,
                ):
                    if r["path"] not in seen:
                        merged.append(r); seen.add(r["path"])
                if len(merged) >= limit:
                    break
            return merged[:limit]
        return self._search_one(
            query=query, category=category, extension=extension,
            date_filter=date_filter, size_filter=size_filter,
            drive=drive, limit=limit, offset=offset,
        )

    def _search_one(
        self,
        query:       str = "",
        category:    str = "",
        extension:   str = "",
        date_filter: str = "",
        size_filter: str = "",
        drive:       str = "",
        limit:       int = 5,
        offset:      int = 0,
    ) -> list[dict]:

        conds, params = [], []

        now = datetime.datetime.now()
        date_map = {
            "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "week":  now - datetime.timedelta(days=7),
            "month": now - datetime.timedelta(days=30),
            "year":  now - datetime.timedelta(days=365),
        }
        if date_filter in date_map:
            conds.append("modified_at >= ?")
            params.append(date_map[date_filter].timestamp())

        if category:
            conds.append("category = ?")
            params.append(category.lower())

        if extension:
            conds.append("extension = ?")
            params.append(extension.lower().lstrip("."))

        size_map = {
            "small":  ("size_bytes < ?",             [1 * 1024 * 1024]),
            "medium": ("size_bytes BETWEEN ? AND ?",  [1 * 1024 * 1024, 100 * 1024 * 1024]),
            "large":  ("size_bytes > ?",              [100 * 1024 * 1024]),
        }
        if size_filter in size_map:
            expr, vals = size_map[size_filter]
            conds.append(expr)
            params.extend(vals)

        # Фильтр по диску: "D" → ищем только файлы на D:\
        if drive:
            conds.append("UPPER(SUBSTR(path, 1, 1)) = ?")
            params.append(drive.upper().strip(": \\"))

        where = ("WHERE " + " AND ".join(conds)) if conds else ""

        if query:
            q = query.lower()
            results, seen = [], set()

            def _run(extra_cond, extra_params, lim):
                all_conds = conds + ([extra_cond] if extra_cond else [])
                all_params = params + extra_params
                w = ("WHERE " + " AND ".join(all_conds)) if all_conds else ""
                sql = f"SELECT * FROM files {w} LIMIT ?"
                with self._lock:
                    return self._conn.execute(sql, all_params + [lim]).fetchall()

            # 1. Точное совпадение
            for r in _run("name_lower = ?", [q], limit):
                if r["path"] not in seen:
                    results.append(dict(r)); seen.add(r["path"])

            # 2. Начинается с запроса
            if len(results) < limit:
                for r in _run("name_lower LIKE ?", [q + "%"], limit * 3):
                    if r["path"] not in seen:
                        results.append(dict(r)); seen.add(r["path"])

            # 3. Содержит запрос целиком
            if len(results) < limit:
                for r in _run("name_lower LIKE ?", ["%" + q + "%"], limit * 5):
                    if r["path"] not in seen:
                        results.append(dict(r)); seen.add(r["path"])

            # 4. AND-поиск по словам — все слова должны быть в имени
            if len(results) < limit:
                words = [w for w in q.split() if len(w) > 2]
                if len(words) > 1:
                    cond = " AND ".join("name_lower LIKE ?" for _ in words)
                    for r in _run(cond, ["%" + w + "%" for w in words], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])
                elif words:
                    for r in _run("name_lower LIKE ?", ["%" + words[0] + "%"], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])

            # 4а. OR-fallback: хотя бы одно слово совпадает
            if len(results) < limit:
                words = [w for w in q.split() if len(w) > 2]
                for word in words:
                    for r in _run("name_lower LIKE ?", ["%" + word + "%"], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])
                    if len(results) >= limit:
                        break

            # 4.5. Поиск в name_search (транслитерированные имена) — AND, потом OR fallback
            if len(results) < limit:
                search_words = [w for w in q.split() if len(w) > 2] or [q]
                if len(search_words) > 1:
                    cond = " AND ".join("name_search LIKE ?" for _ in search_words)
                    for r in _run(cond, ["%" + w + "%" for w in search_words], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])
            if len(results) < limit:
                search_words = [w for w in q.split() if len(w) > 2] or [q]
                for word in search_words:
                    for r in _run("name_search LIKE ?", ["%" + word + "%"], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])
                    if len(results) >= limit:
                        break

            # 5. Fuzzy matching — только если совсем ничего не нашли, пул 500
            # Сравниваем и с name_lower, и с name_search (транслитерированное имя)
            if len(results) < 2 and len(q) > 4:
                sql = f"SELECT * FROM files {where} LIMIT 500"
                with self._lock:
                    pool = self._conn.execute(sql, params).fetchall()
                scored = []
                for r in pool:
                    if r["path"] in seen:
                        continue
                    score = max(
                        SequenceMatcher(None, q, r["name_lower"]).ratio(),
                        SequenceMatcher(None, q, r["name_search"]).ratio(),
                    )
                    if score >= 0.5:
                        scored.append((score, dict(r)))
                scored.sort(key=lambda x: -x[0])
                for score, r in scored:
                    if len(results) < limit:
                        results.append(r); seen.add(r["path"])

            return self._fmt(results[offset: offset + limit])

        # Без запроса — по дате убывания
        sql = f"SELECT * FROM files {where} ORDER BY modified_at DESC LIMIT ? OFFSET ?"
        with self._lock:
            rows = self._conn.execute(sql, params + [limit, offset]).fetchall()
        return self._fmt([dict(r) for r in rows])

    def _fmt(self, rows: list) -> list[dict]:
        out = []
        dead = []   # пути которых больше нет на диске
        for r in rows:
            p = pathlib.Path(r["path"])
            # Пропускаем и помечаем к удалению несуществующие файлы
            if not p.exists():
                dead.append(r["path"])
                continue
            out.append({
                "id":             r.get("id"),
                "name":           r["name"],
                "path":           r["path"],
                "folder":         str(p.parent),
                "extension":      r["extension"],
                "category":       r["category"],
                "size_bytes":     r["size_bytes"],
                "size_human":     _human_size(r["size_bytes"]),
                "modified_at":    r["modified_at"],
                "modified_human": datetime.datetime.fromtimestamp(
                    r["modified_at"]
                ).strftime("%d.%m.%Y %H:%M"),
            })
        # Удаляем мёртвые записи из БД в фоне
        if dead:
            threading.Thread(
                target=self._remove_dead, args=(dead,), daemon=True
            ).start()
        return out

    def _remove_dead(self, paths: list[str]):
        with self._lock:
            self._conn.executemany(
                "DELETE FROM files WHERE path = ?", [(p,) for p in paths]
            )
            self._conn.commit()

    # ── Статистика ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            by_cat = self._conn.execute(
                "SELECT category, COUNT(*) cnt, SUM(size_bytes) total "
                "FROM files GROUP BY category"
            ).fetchall()
            total = self._conn.execute(
                "SELECT COUNT(*), SUM(size_bytes) FROM files"
            ).fetchone()

        cats = {}
        for r in by_cat:
            cats[r["category"]] = {
                "count":      r["cnt"],
                "size_human": _human_size(r["total"] or 0),
            }
        return {
            "total_files": total[0] or 0,
            "total_size":  _human_size(total[1] or 0),
            "by_category": cats,
        }

    def find_duplicates(self, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("""
                SELECT name, size_bytes, COUNT(*) cnt,
                       GROUP_CONCAT(path, '|||') paths
                FROM files
                GROUP BY name_lower, size_bytes
                HAVING cnt > 1
                ORDER BY size_bytes DESC
                LIMIT ?
            """, (limit,)).fetchall()
        result = []
        for r in rows:
            result.append({
                "name":       r["name"],
                "size_human": _human_size(r["size_bytes"]),
                "count":      r["cnt"],
                "paths":      r["paths"].split("|||"),
            })
        return result

    def get_status(self) -> dict:
        with self._lock:
            row   = self._conn.execute(
                "SELECT value FROM meta WHERE key='last_build'"
            ).fetchone()
            count = self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

        last = (
            datetime.datetime.fromtimestamp(float(row["value"])).strftime("%d.%m.%Y %H:%M")
            if row else None
        )
        all_dirs = PRIORITY_DIRS + EXTENDED_DIRS + _get_extra_drives()
        return {
            "total_files":  count,
            "last_build":   last,
            "db_path":      str(DB_PATH),
            "scan_dirs":    [str(d) for d in all_dirs if d.exists()],
            **self.get_progress(),
        }


# ── Синглтон ───────────────────────────────────────────────────────────────────

_indexer: "FileIndexer | None" = None
_indexer_lock = threading.Lock()


def get_indexer() -> FileIndexer:
    global _indexer
    if _indexer is None:
        with _indexer_lock:
            if _indexer is None:
                _indexer = FileIndexer()
    return _indexer