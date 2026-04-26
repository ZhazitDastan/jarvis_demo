import sys
import importlib.util
import pathlib

COMMAND_NAME = "next_search_results"
DESCRIPTION = "Показать следующие результаты поиска файлов (следующие5)."
PARAMETERS = {}
REQUIRED = []

_HERE = pathlib.Path(__file__).parent
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


_ORDINALS = ["Первый", "Второй", "Третий", "Четвёртый", "Пятый"]


def handler() -> str:
    from database.files.file_indexer import get_indexer
    from services.events import emit

    state = _get_state()
    st = state.get_state()
    params = st["params"]
    new_offset = st["offset"] + 5

    indexer = get_indexer()
    results = indexer.search(
        query=params.get("query", ""),
        category=params.get("category", ""),
        date_filter=params.get("date_filter", ""),
        size_filter=params.get("size_filter", ""),
        limit=5,
        offset=new_offset,
    )

    if not results:
        return "Больше результатов нет."

    state.set_results(results, query=params.get("query", ""),
                      offset=new_offset, params=params)

    emit({
        "type": "search_results",
        "results": results,
        "query": params.get("query", ""),
        "offset": new_offset,
    })

    parts = [f"Следующие {len(results)} файла." if len(results) <= 4
             else f"Следующие {len(results)} файлов."]
    for i, r in enumerate(results):
        parts.append(f"{_ORDINALS[i]} — {r['name']}.")
    return " ".join(parts)
