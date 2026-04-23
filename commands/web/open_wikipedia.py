import webbrowser

COMMAND_NAME = "open_wikipedia"
DESCRIPTION = "Открыть статью на Wikipedia по теме"
PARAMETERS = {
    "topic": {
        "type": "string",
        "description": "Тема или название статьи",
    },
    "lang": {
        "type": "string",
        "description": "Язык Wikipedia: ru, en, kk и т.д. По умолчанию — ru",
    },
}
REQUIRED = ["topic"]


def handler(topic: str, lang: str = "ru") -> str:
    url = f"https://{lang}.wikipedia.org/wiki/{topic.replace(' ', '_')}"
    webbrowser.open(url)
    return f"Открываю Wikipedia: {topic}"