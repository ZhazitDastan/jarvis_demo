import webbrowser

COMMAND_NAME = "search_youtube"
DESCRIPTION = "Найти и открыть видео на YouTube"
PARAMETERS = {
    "query": {
        "type": "string",
        "description": "Поисковый запрос для YouTube",
    }
}
REQUIRED = ["query"]


def handler(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Ищу на YouTube: {query}"