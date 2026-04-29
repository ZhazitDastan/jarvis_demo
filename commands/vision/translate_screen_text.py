import config

COMMAND_NAME = "translate_screen_text"
DESCRIPTION = (
    "Translate the text visible on screen to another language / "
    "Перевести текст на экране на другой язык. "
    "RU triggers: переведи текст с экрана, переведи что на экране, переведи с английского на русский на экране. "
    "EN triggers: translate text on screen, translate the screen, what does the screen say in Russian."
)
PARAMETERS = {
    "target_language": {
        "type": "string",
        "description": "Язык перевода, например: русский, английский, Chinese, Spanish",
    }
}
REQUIRED = ["target_language"]


def handler(target_language: str = "русский") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_screen_base64, ask_vision
        b64, _ = grab_screen_base64()
        if is_en:
            prompt = (
                f"Extract all meaningful text from this screenshot and translate it to {target_language}. "
                "Skip UI elements like menu bars and buttons. "
                "Format: show original text then translation for each section."
            )
        else:
            prompt = (
                f"Извлеки весь значимый текст с этого скриншота и переведи на {target_language}. "
                "Пропускай элементы интерфейса: панели меню, кнопки. "
                "Формат: оригинал → перевод для каждого раздела."
            )
        return ask_vision(prompt, b64, max_tokens=600)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"