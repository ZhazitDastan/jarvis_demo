"""
config.py — настройки и проверка окружения
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GPT_MODEL      = "gpt-4o-mini"   # или "gpt-4o"

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL    = "base"           # tiny / base / small / medium / large

# ── Wake word ─────────────────────────────────────────────────────────────────
WAKE_WORD            = "jarvis"
LISTEN_TIMEOUT       = 12        # секунд ждать команду после активации (5-15)
WAKE_CHUNK_DURATION  = 3         # секунд на один кусок при ожидании wake word

# ── Профили языков ────────────────────────────────────────────────────────────
LANGUAGE_PROFILES = {
    "ru": {
        "whisper_language": "ru",
        "tts_voice":        "ru-RU-DmitryNeural",
        "tts_rate":         "+20%",    # быстрее — убирает длинные паузы
        "label":            "Русский",
        "activation":       "Да, сэр?",
        "bye":              "До свидания.",
        "ready":            "Jarvis в сети. Жду команды.",
        "listening":        "Слушаю.",
        "thinking":         "Думаю...",
        "not_heard":        "Не расслышал.",
        "exit_words":       ["выход", "стоп", "пока", "exit", "quit"],
    },
    "en": {
        "whisper_language": "en",
        "tts_voice":        "en-US-GuyNeural",
        "tts_rate":         "+20%",
        "label":            "English",
        "activation":       "Yes, sir?",
        "bye":              "Goodbye.",
        "ready":            "Jarvis online. Awaiting your command.",
        "listening":        "Listening.",
        "thinking":         "Processing...",
        "not_heard":        "Didn't catch that.",
        "exit_words":       ["exit", "quit", "stop", "bye", "выход"],
    },
}

# Активный язык (меняется при старте)
ACTIVE_LANGUAGE = "ru"


def get_lang() -> dict:
    """Возвращает профиль активного языка."""
    return LANGUAGE_PROFILES[ACTIVE_LANGUAGE]


def get_whisper_language() -> str:
    return LANGUAGE_PROFILES[ACTIVE_LANGUAGE]["whisper_language"]

def set_language(lang_code: str):
    global ACTIVE_LANGUAGE
    if lang_code in LANGUAGE_PROFILES:
        ACTIVE_LANGUAGE = lang_code


def build_system_prompt(commands: dict) -> str:
    """Строит системный промпт с учётом доступных команд и языка."""
    lang = ACTIVE_LANGUAGE

    lines = []
    for name, meta in commands.items():
        desc = meta.get("description_en" if lang == "en" else "description", meta["description"])
        lines.append(f'  • "{name}" — {desc}')
    command_block = "\n".join(lines) if lines else "  (команды не добавлены)"

    if lang == "ru":
        return f"""Ты — голосовой ассистент Jarvis.
Отвечай коротко и чётко. Избегай markdown — ответы озвучиваются вслух.
Отвечай на русском языке.

Доступные команды, которые ты умеешь выполнять:
{command_block}

Если пользователь просит выполнить команду — скажи что выполняешь, коротко.
Если спрашивает что ты умеешь — перечисли команды своими словами."""
    else:
        return f"""You are Jarvis, a voice assistant.
Reply briefly and clearly. Avoid markdown — responses are spoken aloud.
Reply in English.

Available commands you can execute:
{command_block}

If the user asks to run a command — say you're executing it, briefly.
If they ask what you can do — list the commands in plain language."""


def check_config() -> bool:
    ok = True
    if not OPENAI_API_KEY:
        print("\n[ERROR] OPENAI_API_KEY not set!")
        print("  Create a .env file and add:")
        print("  OPENAI_API_KEY=sk-your-key-here\n")
        ok = False
    return ok