import config

COMMAND_NAME = "summarize_screen"
DESCRIPTION = (
    "Summarize the content of the current screen — article, document, webpage / "
    "Кратко изложить содержимое экрана: статью, документ, страницу. "
    "RU triggers: кратко изложи что на экране, подведи итог, суммаризируй страницу, о чём эта статья. "
    "EN triggers: summarize the screen, what's this article about, give me a summary, TL DR."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_screen_base64, ask_vision
        b64, _ = grab_screen_base64()
        if is_en:
            prompt = (
                "Summarize the main content visible on this screen. "
                "If it's an article or document — give a 3-4 sentence summary of the key points. "
                "If it's an application — briefly describe what the user is working on. "
                "Be concise and informative."
            )
        else:
            prompt = (
                "Кратко изложи основное содержимое на этом экране. "
                "Если это статья или документ — дай 3-4 предложения с ключевыми мыслями. "
                "Если это приложение — кратко опиши над чем работает пользователь. "
                "Будь лаконичным и информативным."
            )
        return ask_vision(prompt, b64, max_tokens=400, detail="low")
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"