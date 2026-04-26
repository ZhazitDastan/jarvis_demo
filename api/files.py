"""
api/files.py — роуты для поиска и открытия файлов.
Подключается в server.py через app.include_router(router).
"""

import asyncio
import os
import pathlib
import subprocess
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

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
    date_filter: str = "",
    size_filter: str = "",
    limit: int = 5,
    offset: int = 0,
):
    """Поиск файлов по имени, категории, дате, размеру."""
    if not any([q, category, date_filter, size_filter]):
        raise HTTPException(400, "Укажи хотя бы один параметр поиска")

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: _indexer().search(
            query=q,
            category=category,
            date_filter=date_filter,
            size_filter=size_filter,
            limit=limit,
            offset=offset,
        ),
    )
    return {"results": results, "count": len(results)}


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
                # Папка — открываем её напрямую
                os.startfile(req.path)
            else:
                # Файл — открываем родительскую папку с выделением файла
                subprocess.Popen(f'explorer /select,"{req.path}"', shell=True)
        else:
            os.startfile(req.path)
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