import config

COMMAND_NAME = "describe_screen"
DESCRIPTION = (
    "Describe what is currently on the screen / Описать что сейчас на экране. "
    "RU triggers: что на экране, опиши экран, посмотри на экран, что ты видишь. "
    "EN triggers: what's on screen, describe the screen, what do you see."
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
                "Describe what you see on this screenshot in 2-3 sentences. "
                "Focus on what the user is currently doing or viewing. Be concise."
            )
        else:
            prompt = (
                "Опиши что ты видишь на этом скриншоте в 2-3 предложениях. "
                "Сосредоточься на том, чем сейчас занят пользователь. Будь кратким."
            )
        return ask_vision(prompt, b64, max_tokens=300, detail="low")
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"