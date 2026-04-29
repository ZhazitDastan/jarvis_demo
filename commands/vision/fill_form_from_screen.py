import config

COMMAND_NAME = "fill_form_from_screen"
DESCRIPTION = (
    "Analyze a form on screen and describe what fields need to be filled / "
    "Проанализировать форму на экране и описать какие поля нужно заполнить. "
    "RU triggers: что нужно заполнить в этой форме, какие поля в форме, помоги заполнить форму. "
    "EN triggers: what fields are in this form, help me fill the form, analyze this form."
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
                "Analyze the form visible in this screenshot. "
                "List all input fields, dropdowns, checkboxes and other interactive elements. "
                "For each field: its label, type (text/date/select/checkbox), "
                "whether it's required, and what kind of data it expects. "
                "Format as a clear numbered list."
            )
        else:
            prompt = (
                "Проанализируй форму на этом скриншоте. "
                "Перечисли все поля ввода, выпадающие списки, чекбоксы и другие интерактивные элементы. "
                "Для каждого поля: его название, тип (текст/дата/список/чекбокс), "
                "обязательное ли оно и какие данные ожидает. "
                "Оформи в виде пронумерованного списка."
            )
        return ask_vision(prompt, b64, max_tokens=500)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"