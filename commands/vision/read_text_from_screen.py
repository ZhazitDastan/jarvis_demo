import config

COMMAND_NAME = "read_text_from_screen"
DESCRIPTION = (
    "Read and extract all visible text from the screen, including titles, labels, UI elements. "
    "/ Прочитать ВЕСЬ текст с экрана: названия, заголовки, подписи, элементы интерфейса. "
    "Use 'hint' to focus on a specific area or element. "
    "RU triggers: прочитай текст, что написано, прочти, прочти название, прочти имя, "
    "прочти в углу, прочти заголовок, что там написано, прочти в правом углу, "
    "прочти в левом углу, прочти сверху. "
    "EN triggers: read text, what does it say, read the title, read the label, "
    "read the name, read the corner, what's written."
)
PARAMETERS = {
    "hint": {
        "type": "string",
        "description": (
            "Where to look or what to focus on. Examples: "
            "'верхний правый угол', 'заголовок окна', 'левый нижний угол', "
            "'название файла', 'top-right corner', 'window title', 'status bar'."
        ),
    }
}
REQUIRED = []


def handler(hint: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_screen_base64, ask_vision
        b64, _ = grab_screen_base64()

        hint_part = ""
        if hint:
            hint_part = (
                f" Focus specifically on: {hint}."
                if is_en
                else f" Сосредоточься именно на: {hint}."
            )

        if is_en:
            prompt = (
                "Extract ALL visible text from this screenshot — including window titles, "
                "folder names, tab names, labels, buttons, status bars, corner text, "
                "and any other UI elements. Do NOT skip anything."
                + hint_part +
                " If there is a lot of text, prioritize the area mentioned in the focus hint. "
                "State what you see literally — do not say 'the text cannot be determined'."
            )
        else:
            prompt = (
                "Извлеки ВЕСЬ видимый текст с этого скриншота — включая заголовки окон, "
                "названия папок, вкладок, подписи, кнопки, строки состояния, текст в углах "
                "и любые другие элементы интерфейса. НЕ пропускай ничего."
                + hint_part +
                " Если текста много — приоритет на области из подсказки. "
                "Называй буквально что видишь — не говори 'текст не удаётся определить'."
            )
        return ask_vision(prompt, b64, max_tokens=600)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"