import config

COMMAND_NAME = "count_objects_on_screen"
DESCRIPTION = (
    "Count specific objects visible on the screen / "
    "Посчитать определённые объекты на экране. "
    "RU triggers: сколько вкладок открыто, посчитай иконки, сколько окон, сколько файлов на рабочем столе. "
    "EN triggers: how many tabs are open, count the icons, how many windows, count files on desktop."
)
PARAMETERS = {
    "object_type": {
        "type": "string",
        "description": "Тип объекта для подсчёта (вкладки, иконки, файлы, строки и т.д.)",
    }
}
REQUIRED = ["object_type"]


def handler(object_type: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_screen_base64, ask_vision
        b64, _ = grab_screen_base64()
        if is_en:
            prompt = (
                f"Count the number of '{object_type}' visible in this screenshot. "
                "Reply with the count and a brief description of what you counted. "
                "Example: '5 browser tabs are open: Google, YouTube, GitHub, Stack Overflow, Reddit'"
            )
        else:
            prompt = (
                f"Посчитай количество '{object_type}' видимых на этом скриншоте. "
                "Ответь числом и кратким описанием того, что подсчитал. "
                "Пример: 'Открыто 5 вкладок браузера: Google, YouTube, GitHub, Stack Overflow, Reddit'"
            )
        return ask_vision(prompt, b64, max_tokens=300, detail="high")
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"