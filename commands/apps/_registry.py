"""
Реестр приложений — общий для open_app и close_app.
Файл начинается с _ и не загружается автосборщиком как команда.

open_cmd  — список для subprocess.Popen (или shell=True строка)
process   — имя .exe процесса для taskkill
"""
import difflib
import os

_APP = os.environ.get("APPDATA", "")
_LOC = os.environ.get("LOCALAPPDATA", "")
_PRG = os.environ.get("PROGRAMFILES", r"C:\Program Files")
_PRG86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

APP_REGISTRY: dict = {
    # Браузеры
    "chrome":      {"open": ["chrome.exe"],     "process": "chrome.exe"},
    "firefox":     {"open": ["firefox.exe"],     "process": "firefox.exe"},
    "edge":        {"open": ["msedge.exe"],      "process": "msedge.exe"},
    "opera":       {"open": ["opera.exe"],       "process": "opera.exe"},
    "brave":       {"open": ["brave.exe"],       "process": "brave.exe"},

    # Мессенджеры
    "telegram": {
        "open": [os.path.join(_APP, "Telegram Desktop", "Telegram.exe")],
        "process": "Telegram.exe",
    },
    "discord": {
        "open": [os.path.join(_LOC, "Discord", "Update.exe"), "--processStart", "Discord.exe"],
        "process": "Discord.exe",
    },
    "whatsapp": {
        "open": ["WhatsApp.exe"],
        "process": "WhatsApp.exe",
    },
    "skype": {
        "open": ["skype.exe"],
        "process": "Skype.exe",
    },

    # Разработка
    "vscode": {
        "open": ["code"],
        "process": "Code.exe",
        "shell": True,
    },
    "pycharm": {
        "open": ["pycharm64.exe"],
        "process": "pycharm64.exe",
    },
    "notepadpp": {
        "open": [os.path.join(_PRG86, "Notepad++", "notepad++.exe")],
        "process": "notepad++.exe",
    },
    "git": {
        "open": ["git-bash.exe"],
        "process": "git-bash.exe",
        "shell": True,
    },

    # Медиа
    "spotify": {
        "open": [os.path.join(_APP, "Spotify", "Spotify.exe")],
        "process": "Spotify.exe",
    },
    "vlc": {
        "open": [os.path.join(_PRG, "VideoLAN", "VLC", "vlc.exe")],
        "process": "vlc.exe",
    },

    # Системные
    "notepad":     {"open": ["notepad.exe"],     "process": "notepad.exe"},
    "calculator":  {"open": ["calc.exe"],         "process": "CalculatorApp.exe"},
    "explorer":    {"open": ["explorer.exe"],     "process": "explorer.exe"},
    "paint":       {"open": ["mspaint.exe"],      "process": "mspaint.exe"},
    "cmd":         {"open": ["cmd.exe"],          "process": "cmd.exe"},
    "powershell":  {"open": ["powershell.exe"],   "process": "powershell.exe"},
    "taskmgr":     {"open": ["taskmgr.exe"],      "process": "Taskmgr.exe"},

    # Игры
    "steam": {
        "open": [os.path.join(_PRG86, "Steam", "steam.exe")],
        "process": "steam.exe",
    },

    # Офис
    "word":        {"open": ["winword.exe"],      "process": "WINWORD.EXE",  "shell": True},
    "excel":       {"open": ["excel.exe"],        "process": "EXCEL.EXE",    "shell": True},
    "powerpoint":  {"open": ["powerpnt.exe"],     "process": "POWERPNT.EXE", "shell": True},

    # PDF-ридеры
    "acrobat": {
        "open": [os.path.join(_PRG, "Adobe", "Acrobat DC", "Acrobat", "Acrobat.exe")],
        "process": "Acrobat.exe",
    },
    "acrord32": {
        "open": [os.path.join(_PRG86, "Adobe", "Acrobat Reader DC", "Reader", "AcroRd32.exe")],
        "process": "AcroRd32.exe",
    },
    "foxit": {
        "open": [os.path.join(_PRG86, "Foxit Software", "Foxit PDF Reader", "FoxitPDFReader.exe")],
        "process": "FoxitPDFReader.exe",
    },
    "sumatra": {
        "open": [os.path.join(_LOC, "SumatraPDF", "SumatraPDF.exe")],
        "process": "SumatraPDF.exe",
    },

    # Просмотрщики
    "photos":      {"open": ["ms-photos:"],       "process": "Microsoft.Photos.exe", "shell": True},
    "mediaplayer": {"open": ["wmplayer.exe"],      "process": "wmplayer.exe"},
}

# Псевдонимы (синонимы на русском и английском)
ALIASES: dict = {
    # Chrome
    "хром": "chrome", "гугл хром": "chrome", "google chrome": "chrome",
    # Firefox
    "фаерфокс": "firefox", "файерфокс": "firefox", "огненная лиса": "firefox",
    # Edge
    "эдж": "edge", "майкрософт эдж": "edge", "microsoft edge": "edge",
    # Opera
    "опера": "opera",
    # Brave
    "брейв": "brave",
    # Telegram
    "телеграм": "telegram", "телега": "telegram", "тг": "telegram",
    # Discord
    "дискорд": "discord",
    # WhatsApp
    "ватсап": "whatsapp", "вацап": "whatsapp", "вотсап": "whatsapp",
    # Skype
    "скайп": "skype",
    # VS Code
    "вск": "vscode", "редактор кода": "vscode", "код": "vscode",
    "visual studio code": "vscode", "визуал студио": "vscode",
    # PyCharm
    "пайчарм": "pycharm", "пичарм": "pycharm",
    # Notepad++
    "блокнот плюс": "notepadpp", "нотпад плюс": "notepadpp",
    # Spotify
    "спотифай": "spotify", "спотифи": "spotify", "музыка": "spotify",
    # VLC
    "влц": "vlc", "видеоплеер": "vlc", "плеер": "vlc",
    # Системные
    "блокнот": "notepad",
    "калькулятор": "calculator", "счётчик": "calculator",
    "проводник": "explorer", "файлы": "explorer",
    "краска": "paint", "пейнт": "paint", "рисовалка": "paint",
    "командная строка": "cmd", "консоль": "cmd",
    "пауэршелл": "powershell", "оболочка": "powershell",
    "диспетчер задач": "taskmgr", "диспетчер": "taskmgr",
    # Steam
    "стим": "steam", "стим игры": "steam",
    # Office
    "ворд": "word", "текстовый редактор": "word", "microsoft word": "word",
    "ексель": "excel", "эксель": "excel", "таблица": "excel", "таблицы": "excel",
    "паверпоинт": "powerpoint", "презентация": "powerpoint",
    "повер поинт": "powerpoint",
    # PDF
    "акробат": "acrobat", "adobe acrobat": "acrobat", "adobe": "acrobat",
    "acrobat reader": "acrord32", "reader": "acrord32",
    "фоксит": "foxit", "foxit reader": "foxit", "foxit pdf": "foxit",
    "сумatra": "sumatra", "sumatrapdf": "sumatra",
    "пдф": "acrobat", "pdf": "acrobat",
    # Просмотрщики
    "фото": "photos", "просмотр фото": "photos", "галерея": "photos",
    "медиаплеер": "mediaplayer", "windows media": "mediaplayer",
    # Конференции (алиасы → базовое англ. имя, дискавери найдёт точный ключ)
    "вебекс": "webex", "cisco webex": "webex", "цisco": "webex",
    "зум": "zoom", "митинг": "zoom",
    "тимс": "teams", "microsoft teams": "teams",
}


# ── Автообнаружение установленных приложений ─────────────────────────────────
# Загружает _discovery.py через importlib (файл начинается с _ → не автосборщик).

import importlib.util as _util
import pathlib as _pl

_disc_path = _pl.Path(__file__).parent / "_discovery.py"
_disc_spec = _util.spec_from_file_location("_app_discovery", _disc_path)
_disc_mod  = _util.module_from_spec(_disc_spec)
_disc_spec.loader.exec_module(_disc_mod)
_disc_mod.start(APP_REGISTRY)   # сразу кэш + фоновый пересканировщик


def resolve(name: str) -> str | None:
    """Возвращает ключ реестра по имени или псевдониму, или None."""
    key = name.lower().strip()
    if key in APP_REGISTRY:
        return key
    if key in ALIASES:
        target = ALIASES[key]
        if target in APP_REGISTRY:
            return target
        # Alias target not in registry directly — try partial match (e.g. "webex" → "cisco webex")
        for k in APP_REGISTRY:
            if target in k or k in target:
                return k
    # Частичное совпадение по псевдонимам
    for alias, target in ALIASES.items():
        if key in alias or alias in key:
            return target
    # Частичное совпадение по ключам реестра (включая автообнаруженные)
    for k in APP_REGISTRY:
        if key in k or k in key:
            return k
    # Нечёткое совпадение по словам (ловит "зоом"→"zoom", "тимс"→"teams" и т.д.)
    _FUZZY_THRESHOLD = 0.62
    query_words = [w for w in key.split() if len(w) >= 3]
    if not query_words:
        query_words = [key]
    best_score, best_key = 0.0, None
    for k in APP_REGISTRY:
        for qw in query_words:
            for kw in k.split():
                score = difflib.SequenceMatcher(None, qw, kw).ratio()
                if score > best_score:
                    best_score, best_key = score, k
    if best_score >= _FUZZY_THRESHOLD:
        return best_key
    return None