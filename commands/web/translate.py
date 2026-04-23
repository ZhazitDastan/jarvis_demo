import webbrowser
from urllib.parse import quote

COMMAND_NAME = "translate"
DESCRIPTION = "Перевести текст через Google Translate"
PARAMETERS = {
    "text": {
        "type": "string",
        "description": "Текст для перевода",
    },
    "to": {
        "type": "string",
        "description": "Язык перевода: ru, en, kk, de, fr и т.д. По умолчанию ru",
    },
    "from_lang": {
        "type": "string",
        "description": "Исходный язык (auto для автоопределения). По умолчанию auto",
    },
}
REQUIRED = ["text"]


def handler(text: str, to: str = "ru", from_lang: str = "auto") -> str:
    url = (
        f"https://translate.google.com/?sl={from_lang}&tl={to}"
        f"&text={quote(text)}&op=translate"
    )
    webbrowser.open(url)
    return f"Открываю перевод текста на {to}"