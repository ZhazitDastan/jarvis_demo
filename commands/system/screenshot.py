import os
import datetime
import subprocess
import config

COMMAND_NAME = "screenshot"
DESCRIPTION = (
    "Take a screenshot and save to Desktop / Сделать скриншот и сохранить на рабочий стол. "
    "RU triggers: сделай скриншот, скриншот, сфоткай экран, снимок экрана. "
    "EN triggers: take a screenshot, screenshot, capture screen."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(os.path.expanduser("~"), "Desktop", f"screenshot_{ts}.png")

    # Попытка через PIL
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(path)
        return f"Screenshot saved: screenshot_{ts}.png" if is_en else f"Скриншот сохранён: screenshot_{ts}.png"
    except ImportError:
        pass

    # Fallback — PowerShell
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$b = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,"
        "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);"
        "$g = [System.Drawing.Graphics]::FromImage($b);"
        "$g.CopyFromScreen(0,0,0,0,$b.Size);"
        f"$b.Save('{path}');"
        "$g.Dispose(); $b.Dispose()"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=10)
    if r.returncode == 0 and os.path.exists(path):
        return f"Screenshot saved: screenshot_{ts}.png" if is_en else f"Скриншот сохранён: screenshot_{ts}.png"
    return "Screenshot failed." if is_en else "Не удалось сделать скриншот."