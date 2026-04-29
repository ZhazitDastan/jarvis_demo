import config

COMMAND_NAME = "write_content"
DESCRIPTION = (
    "Generate and physically type/paste text at cursor position: code, essay, email, comment. "
    "Use this when user wants text to appear in their editor, browser, or any app. "
    "Сгенерировать и напечатать текст там где курсор: код, эссе, письмо, комментарий. "

    "RU triggers: напиши, напишите, написать, напечатай, напечатайте, вставь текст, "
    "напиши код, напиши функцию, напиши эссе, напиши письмо, напиши сюда, напишите сюда, "
    "можешь написать, можете написать, напиши на python, напиши это, напишите это. "

    "EN triggers: write, type, write code, write an essay, write a letter, type here, "
    "write here, write something, write it, can you write, could you write, "
    "insert text, write in python, please write, go ahead and write."
)
PARAMETERS = {
    "request": {
        "type": "string",
        "description": (
            "Что написать / What to write. "
            "Examples: 'функция сортировки на Python', 'эссе о природе', 'письмо коллеге', "
            "'что видно на экране', 'the folder name from the top right corner'. "
            "If the user just says 'write' or 'напишите' without specifying content, "
            "use 'что видно на экране' (write what's visible on screen)."
        ),
    }
}
REQUIRED = []


def handler(request: str = "") -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        import pyperclip
        import pyautogui
        import time
        from commands.vision._vision_utils import grab_screen_base64
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30.0)

        if not request.strip():
            request = "Write what you see on screen — text, titles, labels, or relevant content." if is_en else "Напиши то что видно на экране — текст, названия, подписи или релевантный контент."

        b64, _ = grab_screen_base64()

        if is_en:
            vision_prompt = (
                "Look at this screenshot and identify: "
                "1) What application/editor is open (VS Code, Notepad, browser, Word, etc.) "
                "2) What programming language if it's a code editor "
                "3) Any relevant context about what's already written. "
                "Reply in 1-2 short sentences only."
            )
        else:
            vision_prompt = (
                "Посмотри на этот скриншот и определи: "
                "1) Какое приложение/редактор открыт (VS Code, Блокнот, браузер, Word и т.д.) "
                "2) Язык программирования если это редактор кода "
                "3) Любой полезный контекст о том что уже написано. "
                "Ответь 1-2 короткими предложениями."
            )

        screen_context = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"}},
                    {"type": "text", "text": vision_prompt},
                ]
            }],
            max_tokens=100,
        ).choices[0].message.content or ""

        if is_en:
            gen_prompt = (
                f"Screen context: {screen_context}\n\n"
                f"Task: {request}\n\n"
                "Generate the requested content. Rules:\n"
                "- Return ONLY the content to type, no explanations\n"
                "- No markdown fences (no ```), just raw text/code\n"
                "- Match the style and language of the current editor context\n"
                "- Be concise but complete"
            )
        else:
            gen_prompt = (
                f"Контекст экрана: {screen_context}\n\n"
                f"Задача: {request}\n\n"
                "Сгенерируй запрошенный контент. Правила:\n"
                "- Верни ТОЛЬКО текст для вставки, без объяснений\n"
                "- Без markdown-блоков (без ```), только чистый текст/код\n"
                "- Соответствуй стилю и языку текущего редактора\n"
                "- Кратко но полно"
            )

        generated = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": gen_prompt}],
            max_tokens=1000,
            temperature=0.4,
        ).choices[0].message.content or ""

        generated = generated.strip()
        if not generated:
            return "Nothing generated." if is_en else "Ничего не сгенерировано."

        pyperclip.copy(generated)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "v")

        lines = generated.count("\n") + 1
        words = len(generated.split())
        if is_en:
            return f"Typed {words} words, {lines} lines."
        else:
            return f"Вставлено {words} слов, {lines} строк."

    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        return f"Install: pip install {missing}"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"