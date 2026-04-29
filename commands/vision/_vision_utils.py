"""
_vision_utils.py — общие утилиты для Vision-команд (не загружается как команда)
"""

import base64
import io
import config

VISION_MODEL = "gpt-4o-mini"

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30.0)
    return _client


def grab_screen_base64(region=None):
    """Делает скриншот (или его область) и возвращает (base64_str, (width, height))."""
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=region)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, img.size


def grab_active_window_base64():
    """Скриншот только активного окна. Fallback — весь экран."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return grab_screen_base64(region=(left, top, right, bottom))
    except Exception:
        return grab_screen_base64()


def grab_clipboard_image_base64():
    """Берёт изображение из буфера обмена. Возвращает (base64_str, size) или (None, None)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            return None, None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return b64, img.size
    except Exception:
        return None, None


def ask_vision(prompt: str, image_base64: str, max_tokens: int = 600, detail: str = "high") -> str:
    """Отправляет изображение в GPT-4o Vision и возвращает текстовый ответ."""
    client = _get_client()
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": detail,
                    }
                },
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
        }],
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()