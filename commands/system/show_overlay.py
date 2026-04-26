COMMAND_NAME = "show_overlay"
DESCRIPTION = (
    "Показать панель/оверлей на экране. / Show an overlay panel on screen. "

    "MODES (use in 'mode' field): "
    "logs     — логи / logs / журнал / журнал событий; "
    "chat     — чат / история чата / история / chat / chat history; "
    "files    — файлы / результаты поиска / найденные файлы / files / search results; "
    "settings — настройки / параметры / settings / preferences. "

    "RU examples: "
    "'покажи логи' → mode=logs; "
    "'открой историю чата' → mode=chat; "
    "'покажи найденные файлы' → mode=files; "
    "'открой настройки' → mode=settings. "

    "EN examples: "
    "'show logs' → mode=logs; "
    "'open chat history' → mode=chat; "
    "'show search results' → mode=files; "
    "'open settings' → mode=settings."
)
PARAMETERS = {
    "mode": {
        "type": "string",
        "description": "logs | chat | files | settings",
        "enum": ["logs", "chat", "files", "settings"],
    },
}
REQUIRED = ["mode"]

_RESPONSES_RU = {
    "logs":     "Открываю логи.",
    "chat":     "Открываю историю чата.",
    "files":    "Открываю результаты поиска.",
    "settings": "Открываю настройки.",
}

_RESPONSES_EN = {
    "logs":     "Opening logs.",
    "chat":     "Opening chat history.",
    "files":    "Opening search results.",
    "settings": "Opening settings.",
}


def handler(mode: str) -> str:
    from services.events import emit
    import config

    emit({"type": "show_overlay", "mode": mode})

    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    responses = _RESPONSES_EN if is_en else _RESPONSES_RU
    return responses.get(mode, f"Открываю {mode}.")