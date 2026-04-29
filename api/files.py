"""
api/files.py — роуты для поиска и открытия файлов.
Подключается в server.py через app.include_router(router).
"""

import asyncio
import ctypes
import os
import pathlib
import subprocess
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


def _open_foreground(path: str) -> None:
    """Открывает файл и выводит окно на передний план.

    os.startfile() из фонового сервиса не получает право на смену фокуса —
    Windows блокирует это (focus stealing prevention). Решение:
    1. AllowSetForegroundWindow(ASFW_ANY) — разрешаем любому процессу вынести окно вперёд
    2. cmd /c start "" — запускает файл в новом процессе с правами на foreground
    """
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
    except Exception:
        pass
    subprocess.Popen(
        f'start "" "{path}"',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

_BLOCKED_EXTS = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1",
                 ".vbs", ".wsf", ".scr", ".pif", ".cpl", ".hta"}

router = APIRouter(prefix="/files", tags=["files"])


def _indexer():
    from database.files.file_indexer import get_indexer
    return get_indexer()


# ── Модели ────────────────────────────────────────────────────────────────────

class FileOpenRequest(BaseModel):
    path: str
    action: str = "open"   # "open" | "folder"


# ── Роуты ─────────────────────────────────────────────────────────────────────

@router.get("/search")
async def files_search(
    q: str = "",
    category: str = "",
    extension: str = "",
    date_filter: str = "",
    size_filter: str = "",
    drive: str = "",
    semantic: bool = False,
    limit: int = 20,
    offset: int = 0,
):
    """Поиск файлов по имени или содержимому (semantic=true)."""
    if not any([q, category, extension, date_filter, size_filter, drive]):
        raise HTTPException(400, "Укажи хотя бы один параметр поиска")

    drive_norm = drive.upper().strip(": \\") if drive else ""
    loop       = asyncio.get_event_loop()

    # ── Параллельный запуск семантики и поиска по имени ──────────────────────
    # Раньше шло последовательно: semantic (~1-2с на embedding) → name search.
    # Теперь оба запускаются одновременно — суммарное время = max, не sum.
    name_task = loop.run_in_executor(
        None,
        lambda: _indexer().search(
            query=q,
            category=category,
            extension=extension,
            date_filter=date_filter,
            size_filter=size_filter,
            drive=drive_norm,
            limit=limit,
            offset=offset,
        ),
    )

    sem_task = None
    if semantic and q:
        import config
        api_key = getattr(config, "OPENAI_API_KEY", "")
        if not api_key:
            raise HTTPException(400, "OpenAI API ключ не задан — семантический поиск недоступен")
        from database.files.semantic_search import get_semantic_indexer
        sem_task = loop.run_in_executor(
            None,
            lambda: get_semantic_indexer().search(
                query=q, api_key=api_key, limit=limit, category=category,
            ),
        )

    results: list = []
    seen:    set  = set()

    # Семантика идёт первой в ответе, если включена
    if sem_task is not None:
        for r in await sem_task:
            results.append(r)
            seen.add(r["path"])

    for r in await name_task:
        if r["path"] not in seen:
            results.append(r)
            seen.add(r["path"])

    return {
        "results":  results[:limit],
        "total":    len(results),
        "offset":   offset,
        "limit":    limit,
        "semantic": semantic,
    }


@router.post("/open")
async def file_open(req: FileOpenRequest):
    """Открыть файл или папку с файлом."""
    if not os.path.exists(req.path):
        raise HTTPException(404, f"Путь не найден: {req.path}")
    ext = pathlib.Path(req.path).suffix.lower()
    if req.action == "open" and ext in _BLOCKED_EXTS:
        raise HTTPException(403, f"Открытие исполняемых файлов ({ext}) заблокировано")
    try:
        if req.action == "folder":
            if os.path.isdir(req.path):
                _open_foreground(req.path)
            else:
                # Файл — открываем родительскую папку с выделением файла
                try:
                    ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)
                except Exception:
                    pass
                subprocess.Popen(
                    f'explorer /select,"{req.path}"',
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        else:
            _open_foreground(req.path)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/index/status")
async def file_index_status():
    """Статус индекса: количество файлов, дата индексации, список сканируемых папок."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _indexer().get_status)


@router.get("/index/progress")
async def file_index_progress():
    """Текущий прогресс индексации: percent, scanned, total, is_indexing."""
    return _indexer().get_progress()


@router.post("/index/rebuild")
async def file_index_rebuild():
    """Запустить переиндексацию файлов в фоновом потоке."""
    from services.events import emit

    def _bg():
        count = _indexer().build_index()
        emit({"type": "index_rebuilt", "total_files": count})

    threading.Thread(target=_bg, daemon=True).start()
    return {"ok": True, "message": "Переиндексация запущена"}


@router.get("/index/rebuild")
async def file_index_rebuild_get(request: Request):
    """GET-алиас для браузера — только с localhost."""
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Только для локального доступа")
    from services.events import emit

    def _bg():
        count = _indexer().build_index()
        emit({"type": "index_rebuilt", "total_files": count})

    threading.Thread(target=_bg, daemon=True).start()
    return {"ok": True, "message": "Переиндексация запущена"}


@router.get("/stats")
async def file_stats():
    """Статистика файлов по категориям и размеру."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _indexer().get_stats)


# ── Семантический индекс ──────────────────────────────────────────────────────

@router.get("/semantic/status")
async def semantic_status():
    """Статус семантического индекса: кол-во проиндексированных файлов, прогресс."""
    from database.files.semantic_search import get_semantic_indexer
    return get_semantic_indexer().get_status()


@router.post("/semantic/rebuild")
async def semantic_rebuild():
    """Запустить переиндексацию семантического индекса в фоне."""
    import config
    api_key = getattr(config, "OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(400, "OpenAI API ключ не задан")

    from database.files.semantic_search import get_semantic_indexer, ALL_SUPPORTED
    from services.events import emit

    def _bg():
        try:
            # Берём все документы из file indexer БД
            indexer = _indexer()
            with indexer._lock:
                rows = indexer._conn.execute(
                    "SELECT path FROM files WHERE extension IN ({})".format(
                        ",".join("?" * len(ALL_SUPPORTED))
                    ),
                    list(ALL_SUPPORTED),
                ).fetchall()
            paths = [r["path"] for r in rows]
            count = get_semantic_indexer().build_index(paths, api_key)
            emit({"type": "semantic_index_done", "indexed": count})
        except Exception as e:
            emit({"type": "semantic_index_error", "error": str(e)})

    threading.Thread(target=_bg, daemon=True, name="semantic-rebuild").start()
    return {"ok": True, "message": "Семантическая переиндексация запущена"}