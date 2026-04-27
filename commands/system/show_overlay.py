COMMAND_NAME = "show_overlay"
DESCRIPTION = (
    "Показать или закрыть панель/оверлей на экране. / Show or close an overlay panel. "

    "MODES (use in 'mode' field): "
    "logs     — логи / logs / журнал; "
    "chat     — чат / история чата / chat history; "
    "files    — файлы / результаты поиска / files / search results; "
    "settings — настройки / параметры / settings; "
    "close    — закрыть / скрыть / убери панель / close / hide / dismiss. "

    "RU examples: "
    "'покажи логи' → mode=logs; "
    "'открой настройки' → mode=settings; "
    "'закрой панель' → mode=close; "
    "'убери оверлей' → mode=close. "

    "EN examples: "
    "'show logs' → mode=logs; "
    "'close panel' → mode=close; "
    "'hide overlay' → mode=close."
)
PARAMETERS = {
    "mode": {
        "type": "string",
        "description": "logs | chat | files | settings | close",
        "enum": ["logs", "chat", "files", "settings", "close"],
    },
}
REQUIRED = ["mode"]

_RESPONSES_RU = {
    "logs":     "Открываю логи.",
    "chat":     "Открываю историю чата.",
    "files":    "Открываю результаты поиска.",
    "settings": "Открываю настройки.",
    "close":    "Закрываю панель.",
}

_RESPONSES_EN = {
    "logs":     "Opening logs.",
    "chat":     "Opening chat history.",
    "files":    "Opening search results.",
    "settings": "Opening settings.",
    "close":    "Closing panel.",
}


def handler(mode: str) -> str:
    from services.events import emit
    import config

    if mode == "close":
        emit({"type": "close_overlay"})
    else:
        emit({"type": "show_overlay", "mode": mode})

    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    responses = _RESPONSES_EN if is_en else _RESPONSES_RU
    return responses.get(mode, f"Открываю {mode}.")