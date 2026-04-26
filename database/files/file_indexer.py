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


def _query_variants(query: str) -> list[str]:
    """Оригинал + транслитерированная версия (RU→EN или EN→RU).
    Транслитерируем только если запрос длиннее 4 символов —
    короткие слова дают слишком много ложных совпадений.
    """
    if not query or len(query.strip()) <= 4:
        return [query]
    q = query.lower()
    has_cyr = any('Ѐ' <= c <= 'ӿ' for c in q)
    has_lat = any('a' <= c <= 'z' for c in q)
    variants = [q]
    if has_cyr and not has_lat:
        alt = _to_latin(q)
        if alt != q:
            variants.append(alt)
    elif has_lat and not has_cyr:
        alt = _to_cyrillic(q)
        if alt != q:
            variants.append(alt)
    return variants

DB_PATH = pathlib.Path(__file__).parent / "files.db"

HOME = pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home())))

# ── Приоритеты сканирования ────────────────────────────────────────────────────
# Фаза 1: самые важные папки — результаты через ~5-10 сек
PRIORITY_DIRS = [
    HOME / "Desktop",
    HOME / "OneDrive" / "Рабочий стол",
    HOME / "OneDrive" / "Desktop",
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "OneDrive" / "Documents",
]

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
    # AppData мусор
    "appdata\\local\\temp", "appdata\\roaming\\microsoft",
    "appdata\\local\\microsoft", "appdata\\local\\google",
    "appdata\\local\\packages",
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
                indexed_at  REAL NOT NULL
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

    def _auto_build_and_watch(self):
        """Запускается в фоне при старте: rebuild если нужно, потом watchdog."""
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
            print(f"    [cleanup] Удалено устаревших записей: {total_removed}")

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
                    "(name, name_lower, path, extension, category, size_bytes, modified_at, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (fpath.name, fpath.name.lower(), str(fpath),
                     ext.lower().lstrip("."), cat, size, stat.st_mtime, time.time()),
                )
                self._conn.commit()
        except (OSError, PermissionError):
            pass

    # обратная совместимость
    def _index_file(self, path: str):
        self._index_path(path)

    def _remove_file(self, path: str):
        """Удалить файл из индекса."""
        with self._lock:
            self._conn.execute("DELETE FROM files WHERE path = ?", (path,))
            self._conn.commit()

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
                    _schedule(event.src_path, "add")

                def on_deleted(self, event):
                    _schedule(event.src_path, "remove")

                def on_moved(self, event):
                    _schedule(event.src_path, "remove")
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
                    print(f"    [watcher] Слежу: {d}")

            observer.daemon = True
            observer.start()
            self._observer = observer
            print(f"    [watcher] Запущен. Папок под наблюдением: {len(watched)}")

        except ImportError:
            print("    [watcher] watchdog не установлен (pip install watchdog)")
        except Exception as e:
            print(f"    [watcher] Ошибка запуска: {e}")

    def _flush(self, batch: list[tuple]):
        """Записывает батч файлов в БД — не блокирует поиск надолго."""
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO files "
                "(name, name_lower, path, extension, category, size_bytes, modified_at, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
        limit:       int = 5,
        offset:      int = 0,
    ) -> list[dict]:
        # Ищем по оригинальному запросу + транслитерированному варианту
        variants = _query_variants(query)
        if len(variants) > 1:
            seen, merged = set(), []
            for v in variants:
                for r in self._search_one(
                    query=v, category=category, extension=extension,
                    date_filter=date_filter, size_filter=size_filter,
                    limit=limit, offset=offset,
                ):
                    if r["path"] not in seen:
                        merged.append(r); seen.add(r["path"])
                if len(merged) >= limit:
                    break
            return merged[:limit]
        return self._search_one(
            query=query, category=category, extension=extension,
            date_filter=date_filter, size_filter=size_filter,
            limit=limit, offset=offset,
        )

    def _search_one(
        self,
        query:       str = "",
        category:    str = "",
        extension:   str = "",
        date_filter: str = "",
        size_filter: str = "",
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

            # 4. Поиск по отдельным словам (для запросов типа "диплом финал")
            if len(results) < limit:
                words = [w for w in q.split() if len(w) > 2]
                for word in words:
                    for r in _run("name_lower LIKE ?", ["%" + word + "%"], limit * 3):
                        if r["path"] not in seen:
                            results.append(dict(r)); seen.add(r["path"])
                    if len(results) >= limit:
                        break

            # 5. Fuzzy matching — только если совсем ничего не нашли, пул 500
            if len(results) < 2 and len(q) > 4:
                sql = f"SELECT * FROM files {where} LIMIT 500"
                with self._lock:
                    pool = self._conn.execute(sql, params).fetchall()
                scored = [
                    (SequenceMatcher(None, q, r["name_lower"]).ratio(), dict(r))
                    for r in pool if r["path"] not in seen
                ]
                scored.sort(key=lambda x: -x[0])
                for score, r in scored:
                    if score >= 0.5 and len(results) < limit:
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