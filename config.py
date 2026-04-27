"""
config.py — настройки и проверка окружения
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
GPT_MODEL       = "gpt-4o-mini"   # или "gpt-4o"
GPT_TEMPERATURE = 0.7

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL    = "base"           # tiny / base / small / medium / large

# ── Vosk ──────────────────────────────────────────────────────────────────────
# vosk-model-small-ru-0.22       (~45 MB,  быстро, менее точно)
# vosk-model-ru-0.42             (~2.6 GB, медленно загружается, точнее)
VOSK_MODEL_DIR    = "models/vosk-model-small-ru-0.22"
# vosk-model-en-us-0.22-lgraph   (~128 MB, быстрая EN модель для wake word)
VOSK_EN_MODEL_DIR = "models/vosk-model-en-us-0.22-lgraph"

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
        "not_understood":   "Не понял, повторите.",
        "stopped":          "Хорошо.",
        "exit_words":       ["выход", "пока", "exit", "quit"],
        "stop_words":       ["стоп", "хватит", "замолчи", "тихо", "достаточно", "молчать"],
    },
    "en": {
        "whisper_language": "en",
        "tts_voice":        "en-GB-RyanNeural",
        "tts_rate":         "+20%",
        "label":            "English",
        "activation":       "Yes, sir?",
        "bye":              "Goodbye.",
        "ready":            "Jarvis online. Awaiting your command.",
        "listening":        "Listening.",
        "thinking":         "Processing...",
        "not_heard":        "Didn't catch that.",
        "not_understood":   "Didn't catch that, please repeat.",
        "stopped":          "Okay.",
        "exit_words":       ["exit", "quit", "bye", "goodbye", "выход"],
        "stop_words":       ["stop", "enough", "quiet", "silence", "cancel", "shut up"],
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
Отвечай коротко и чётко, максимум 1-2 предложения. Избегай markdown — ответы озвучиваются вслух.
Отвечай на том языке, на котором говорит пользователь (русский или английский).

Доступные команды, которые ты умеешь выполнять:
{command_block}

Правила:
- Если пользователь просит выполнить команду из списка — вызови её, не объясняй.
- Если спрашивает что ты умеешь — перечисли команды своими словами кратко.
- Если команда понятна, но не хватает уточнения — задай один короткий вопрос.
  Примеры: "На диске C или D?", "Имя файла на русском или английском?", "Какую папку открыть?"
- На общие вопросы (факты, математика, история, советы и т.д.) — отвечай из своих знаний, коротко.
- Если совсем не понял речь — скажи только: "Не понял, повторите."
- Если пользователь просит действие которое ты не умеешь выполнить — скажи только: "Не могу это сделать."
- Никогда не придумывай команды которых нет в списке."""
    else:
        return f"""You are Jarvis, a voice assistant.
Reply briefly and clearly, 1-2 sentences max. Avoid markdown — responses are spoken aloud.
Reply in the language the user speaks (Russian or English).

Available commands you can execute:
{command_block}

Rules:
- If the user asks to run a command from the list — call it, don't explain.
- If they ask what you can do — briefly list the commands.
- If the command is clear but a detail is missing — ask one short clarifying question.
  Examples: "Drive C or D?", "File name in Russian or English?", "Which folder?"
- For general questions (facts, math, history, advice, etc.) — answer from your own knowledge, briefly.
- If you didn't understand the speech at all — say only: "Didn't catch that, please repeat."
- If the user asks for an action you can't perform — say only: "I can't do that."
- Never invent commands that aren't in the list."""


def check_config() -> bool:
    ok = True
    if not OPENAI_API_KEY:
        print("\n[ERROR] OPENAI_API_KEY not set!")
        print("  Create a .env file and add:")
        print("  OPENAI_API_KEY=sk-your-key-here\n")
        ok = False
    return ok