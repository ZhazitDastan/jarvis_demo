import importlib.util
import pathlib
import config

# Загружаем _helpers.py напрямую по пути — избегаем дедлока с commands/__init__.py
_h_spec = importlib.util.spec_from_file_location(
    "_search_helpers", pathlib.Path(__file__).parent / "_helpers.py"
)
_h = importlib.util.module_from_spec(_h_spec)
_h_spec.loader.exec_module(_h)
get_state = _h.get_state
format_results = _h.format_results
CAT_RU = _h.CAT_RU
CAT_EN = _h.CAT_EN

COMMAND_NAME = "search_by_content"
DESCRIPTION = (
    "Search for files BY CONTENT (semantic meaning/topic). "
    "/ Поиск файлов по СОДЕРЖИМОМУ (смысл/тема). "

    "Use this command when the user describes WHAT IS INSIDE the file, not its name. "
    "Do NOT use this if the user just says a filename — use search_by_name instead. "

    "RU triggers: "
    "'найди файл где я писал про нейросети' → query=нейросети; "
    "'найди документ о машинном обучении' → query=машинное обучение; "
    "'где мой отчёт про продажи' → query=продажи; "
    "'найди где написано про авторизацию' → query=авторизация. "

    "EN triggers: "
    "'find file about neural networks' → query=neural networks; "
    "'find where I wrote about authentication' → query=authentication; "
    "'find document about sales report' → query=sales report; "
    "'find file that mentions machine learning' → query=machine learning. "

    "CATEGORY filter (optional — only set when user explicitly mentions file type): "
    "document — документ/doc/pdf/word. "
    "code — код/скрипт/code/script. "
    "photo/video/music — only if user says so explicitly."
)
PARAMETERS = {
    "query": {
        "type": "string",
        "description": (
            "Topic or meaning to search for inside files. "
            "/ Тема или смысл для поиска внутри файлов. "
            "Examples: 'neural networks', 'продажи за квартал', 'authentication flow'."
        ),
    },
    "category": {
        "type": "string",
        "description": (
            "Optional file type filter: document, code, photo, video, music, archive. "
            "Set only when user explicitly mentions a file type."
        ),
        "enum": ["folder", "document", "photo", "video", "music", "archive", "code"],
    },
}
REQUIRED = ["query"]


def handler(query: str = "", category: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    if not query.strip():
        return (
            "Please describe what the file is about."
            if is_en else
            "Опиши о чём файл — что в нём написано или какая тема."
        )

    try:
        from database.files.semantic_search import get_semantic_indexer
        from services.events import emit

        api_key = getattr(config, "OPENAI_API_KEY", "")
        results = get_semantic_indexer().search(
            query=query,
            api_key=api_key,
            limit=5,
            category=category,
        )
    except Exception as e:
        print(f"  [search_by_content] Ошибка: {e}")
        return (
            "Content search failed. Check that the index is built."
            if is_en else
            "Ошибка поиска по содержимому. Проверь что индекс построен."
        )

    state = get_state()
    state.set_results(
        results,
        query=query,
        offset=0,
        params={"query": query, "category": category, "semantic": True},
    )

    emit({
        "type": "search_results",
        "results": results,
        "query": query, "category": category, "semantic": True,
        "total_shown": len(results),
    })

    if not results:
        return (
            f"Nothing found by content for '{query}'. "
            "The file may not be indexed yet — try rebuilding the index."
            if is_en else
            f"Ничего не нашёл по содержимому для «{query}». "
            "Возможно файл ещё не проиндексирован — попробуй переиндексировать."
        )

    return format_results(results, is_en)