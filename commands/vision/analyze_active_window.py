import config

COMMAND_NAME = "analyze_active_window"
DESCRIPTION = (
    "Analyze the currently active window / Проанализировать активное окно. "
    "RU triggers: проанализируй активное окно, что в текущем окне, посмотри на окно, анализ окна. "
    "EN triggers: analyze active window, what's in this window, look at the current window."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_active_window_base64, ask_vision
        b64, _ = grab_active_window_base64()
        if is_en:
            prompt = (
                "Analyze the content of this window. What application is it? "
                "What is the user doing? What key information or actions are visible? "
                "Be concise, 2-4 sentences."
            )
        else:
            prompt = (
                "Проанализируй содержимое этого окна. Что это за приложение? "
                "Чем занимается пользователь? Какая ключевая информация или действия видны? "
                "Кратко, 2-4 предложения."
            )
        return ask_vision(prompt, b64, max_tokens=400, detail="low")
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"