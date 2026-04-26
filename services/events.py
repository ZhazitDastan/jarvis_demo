"""
Шина событий — позволяет командам отправлять события в WebSocket
без прямого импорта api/server.py (избегает circular import).
"""

import threading

_fn = None
_lock = threading.Lock()


def register_emit(fn):
    global _fn
    with _lock:
        _fn = fn


def emit(event: dict):
    with _lock:
        fn = _fn
    if fn:
        fn(event)

