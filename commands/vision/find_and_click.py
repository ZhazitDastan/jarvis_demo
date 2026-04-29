import config

COMMAND_NAME = "find_and_click"
DESCRIPTION = (
    "Find a UI element by name on the screen and click it / "
    "Найти элемент интерфейса по названию и кликнуть на него. "
    "RU triggers: нажми на кнопку, кликни на, найди и нажми, нажми кнопку X. "
    "EN triggers: click on button, find and click, press the button."
)
PARAMETERS = {
    "element": {
        "type": "string",
        "description": "Название элемента для клика (кнопка, ссылка, иконка)",
    }
}
REQUIRED = ["element"]


def handler(element: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        import pyautogui
        from commands.vision._vision_utils import grab_screen_base64, ask_vision
        b64, (w, h) = grab_screen_base64()

        if is_en:
            prompt = (
                f"Find the UI element '{element}' on this screenshot. "
                f"The screen resolution is {w}x{h} pixels. "
                "Reply ONLY with two integers separated by a comma: X,Y (pixel coordinates of the element center). "
                "If you cannot find the element, reply with: NOT_FOUND"
            )
        else:
            prompt = (
                f"Найди элемент интерфейса '{element}' на этом скриншоте. "
                f"Разрешение экрана: {w}x{h} пикселей. "
                "Ответь ТОЛЬКО двумя числами через запятую: X,Y (координаты центра элемента в пикселях). "
                "Если элемент не найден — ответь: NOT_FOUND"
            )

        result = ask_vision(prompt, b64, max_tokens=50, detail="high")

        if "NOT_FOUND" in result.upper():
            return f"Element '{element}' not found on screen." if is_en else f"Элемент '{element}' не найден на экране."

        coords = result.strip().split(",")
        x, y = int(coords[0].strip()), int(coords[1].strip())
        pyautogui.click(x, y)
        return f"Clicked on '{element}' at {x},{y}." if is_en else f"Кликнул на '{element}' в позиции {x},{y}."

    except ImportError:
        missing = []
        try:
            import pyautogui  # noqa
        except ImportError:
            missing.append("pyautogui")
        try:
            from PIL import ImageGrab  # noqa
        except ImportError:
            missing.append("Pillow")
        return f"Install: pip install {' '.join(missing)}"
    except (ValueError, IndexError):
        return f"Could not parse coordinates for '{element}'." if is_en else f"Не удалось определить координаты '{element}'."
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"