import config

COMMAND_NAME = "check_errors_on_screen"
DESCRIPTION = (
    "Check screen for errors, warnings or problems / "
    "Проверить экран на наличие ошибок, предупреждений или проблем. "
    "RU triggers: есть ли ошибки на экране, проверь на ошибки, что за ошибка, что-то сломалось. "
    "EN triggers: any errors on screen, check for errors, what's the error, something is broken."
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
                "Scan this screenshot for any errors, warnings, exceptions, crash dialogs, "
                "or problem indicators (red text, error icons, stack traces, HTTP errors, etc.). "
                "If errors found: describe each briefly and suggest a fix if possible. "
                "If no errors: say 'No errors detected on screen'."
            )
        else:
            prompt = (
                "Проверь этот скриншот на наличие ошибок, предупреждений, исключений, диалогов сбоев, "
                "или признаков проблем (красный текст, иконки ошибок, stack traces, HTTP-ошибки и т.д.). "
                "Если ошибки найдены: кратко опиши каждую и предложи решение, если возможно. "
                "Если ошибок нет — скажи 'Ошибок на экране не обнаружено'."
            )
        return ask_vision(prompt, b64, max_tokens=500)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"