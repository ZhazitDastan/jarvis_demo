import time
import config

COMMAND_NAME = "chrome_open_url"
DESCRIPTION = (
    "Open a URL directly in Chrome address bar / "
    "Открыть URL прямо в адресной строке Chrome. "
    "RU triggers: открой сайт, перейди на сайт, введи адрес, открой в хроме. "
    "EN triggers: open website, go to site, navigate to, open in chrome."
)
PARAMETERS = {
    "url": {
        "type": "string",
        "description": "URL или домен сайта, например: youtube.com или https://github.com",
    }
}
REQUIRED = ["url"]


def handler(url: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    if not url.startswith("http"):
        url = "https://" + url
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite(url, interval=0.03)
        pyautogui.press("enter")
        return f"Opening {url}" if is_en else f"Открываю {url}"
    except ImportError:
        return "Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"