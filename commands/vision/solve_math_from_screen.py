import config

COMMAND_NAME = "solve_math_from_screen"
DESCRIPTION = (
    "Find and solve a math problem or formula visible on the screen / "
    "Найти и решить математическую задачу или формулу на экране. "
    "RU triggers: реши задачу с экрана, реши пример на экране, посчитай формулу с экрана, реши уравнение. "
    "EN triggers: solve math on screen, calculate the formula on screen, solve the equation on screen."
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
                "Find any math problem, equation, or formula on this screenshot and solve it. "
                "Show the solution step by step, briefly. "
                "If there is no math on the screen, say 'No math found on screen'."
            )
        else:
            prompt = (
                "Найди на этом скриншоте математическую задачу, уравнение или формулу и реши её. "
                "Покажи решение пошагово, кратко. "
                "Если математики на экране нет — скажи 'Математических задач на экране не найдено'."
            )
        return ask_vision(prompt, b64, max_tokens=500)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"