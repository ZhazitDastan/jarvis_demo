"""
 Разделяемое состояние для поисковых команд.
 Хранит последние результаты поиска для голосовой навигации.
 """

import threading

_lock = threading.Lock()
_results: list = []
_query: str = ""
_offset: int = 0
_last_params: dict = {}


def set_results(results: list, query: str = "", offset: int = 0, params:
dict = None):
    with _lock:
        global _results, _query, _offset, _last_params
        _results = results
        _query = query
        _offset = offset
        _last_params = params or {}


def get_results() -> list:
    with _lock:
        return list(_results)


def get_state() -> dict:
    with _lock:
        return {
            "results": list(_results),
            "query": _query,
            "offset": _offset,
            "params": dict(_last_params),
        }


def get_offset() -> int:
    with _lock:
        return _offset


def set_offset(offset: int):
    with _lock:
        global _offset
        _offset = offset
