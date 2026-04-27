import sys
import importlib.util
import pathlib

COMMAND_NAME = "next_search_results"
DESCRIPTION = (
    "Show next page of file search results. / Показать следующие результаты поиска файлов. "
    "RU triggers: следующие, ещё, ещё результаты, дальше, больше файлов. "
    "EN triggers: next, more results, show more, next page."
)
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


_ORDINALS_RU = ["Первый", "Второй", "Третий", "Четвёртый", "Пятый"]
_ORDINALS_EN = ["First",  "Second", "Third",  "Fourth",    "Fifth"]


def handler() -> str:
    import config
    from database.files.file_indexer import get_indexer
    from services.events import emit

    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    state = _get_state()
    st = state.get_state()
    params = st["params"]
    new_offset = st["offset"] + 5

    indexer = get_indexer()
    results = indexer.search(
        query=params.get("query", ""),
        category=params.get("category", ""),
        extension=params.get("extension", ""),
        date_filter=params.get("date_filter", ""),
        size_filter=params.get("size_filter", ""),
        drive=params.get("drive", ""),
        limit=5,
        offset=new_offset,
    )

    if not results:
        return "No more results." if is_en else "Больше результатов нет."

    state.set_results(results, query=params.get("query", ""),
                      offset=new_offset, params=params)

    emit({
        "type":    "search_results",
        "results": results,
        "query":   params.get("query", ""),
        "offset":  new_offset,
    })

    ordinals = _ORDINALS_EN if is_en else _ORDINALS_RU
    if is_en:
        parts = [f"Next {len(results)} files."]
        for i, r in enumerate(results):
            parts.append(f"{ordinals[i]} — {r['name']}.")
        parts.append("Say 'first', 'second', and so on to open.")
    else:
        count_word = "файла" if len(results) <= 4 else "файлов"
        parts = [f"Следующие {len(results)} {count_word}."]
        for i, r in enumerate(results):
            parts.append(f"{ordinals[i]} — {r['name']}.")
        parts.append("Скажи «первый», «второй» и так далее чтобы открыть.")
    return " ".join(parts)
