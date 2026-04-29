import time
import config

COMMAND_NAME = "whats_changed"
DESCRIPTION = (
    "Take two screenshots with a delay and describe what changed on screen / "
    "Сделать два скриншота с паузой и описать что изменилось на экране. "
    "RU triggers: что изменилось на экране, следи за экраном, что поменялось. "
    "EN triggers: what changed on screen, watch the screen, what's different now."
)
PARAMETERS = {
    "delay_seconds": {
        "type": "integer",
        "description": "Пауза между снимками в секундах (по умолчанию 5)",
        "default": 5,
    }
}
REQUIRED = []


def handler(delay_seconds: int = 5) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    delay_seconds = max(2, min(delay_seconds, 30))
    try:
        from commands.vision._vision_utils import grab_screen_base64
        from openai import OpenAI

        b64_before, _ = grab_screen_base64()
        print(f"  [vision] {'Watching' if is_en else 'Слежу'} {delay_seconds}s...")
        time.sleep(delay_seconds)
        b64_after, _ = grab_screen_base64()

        client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30.0)

        if is_en:
            prompt = (
                "I have two screenshots taken a few seconds apart. "
                "The FIRST image is 'before', the SECOND is 'after'. "
                "Describe concisely what changed between them. "
                "Focus on meaningful changes: new windows, dialogs, text, notifications. "
                "If nothing changed, say 'Nothing significant changed'."
            )
        else:
            prompt = (
                "У меня два скриншота, сделанных с паузой в несколько секунд. "
                "ПЕРВОЕ изображение — 'до', ВТОРОЕ — 'после'. "
                "Кратко опиши что изменилось между ними. "
                "Фокусируйся на значимых изменениях: новые окна, диалоги, текст, уведомления. "
                "Если ничего не изменилось — скажи 'Значимых изменений не обнаружено'."
            )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_before}", "detail": "low"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_after}", "detail": "low"}},
                    {"type": "text", "text": prompt},
                ]
            }],
            max_tokens=400,
        )
        return (response.choices[0].message.content or "").strip()

    except ImportError:
        return "Install Pillow: pip install Pillow" if is_en else "Установите Pillow: pip install Pillow"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"