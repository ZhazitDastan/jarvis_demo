import config

COMMAND_NAME = "read_clipboard_image"
DESCRIPTION = (
    "Analyze an image from the clipboard / Проанализировать изображение из буфера обмена. "
    "RU triggers: проанализируй картинку из буфера, опиши изображение из буфера, что в буфере обмена, прочитай картинку. "
    "EN triggers: analyze clipboard image, describe clipboard picture, what's in clipboard."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        from commands.vision._vision_utils import grab_clipboard_image_base64, ask_vision
        b64, _ = grab_clipboard_image_base64()
        if b64 is None:
            return "No image in clipboard." if is_en else "В буфере обмена нет изображения."
        if is_en:
            prompt = (
                "Describe this image in detail. What does it show? "
                "If it contains text, read it. If it's a diagram or chart, explain it. "
                "Be thorough but concise."
            )
        else:
            prompt = (
                "Подробно опиши это изображение. Что на нём изображено? "
                "Если есть текст — зачитай его. Если это диаграмма или график — объясни. "
                "Будь подробным, но кратким."
            )
        return ask_vision(prompt, b64, max_tokens=500)
    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"