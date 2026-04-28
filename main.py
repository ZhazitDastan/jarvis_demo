"""
Jarvis — Голосовой ассистент
Запуск: python main.py

Цикл работы:
  1. Слушаем "Jarvis" (непрерывно, без Enter)
  2. Записываем команду с VAD (стоп по тишине, макс 15 сек)
  3. STT → GPT → TTS


  4. После ответа — ещё FOLLOWUP_SECONDS секунд слушаем без wake word
     (продолжение диалога без повторного "Jarvis")
  5. Возвращаемся к шагу 1
"""

import sys
import os

# JetBrains запускает Python без полного PATH — torch и onnxruntime не находят свои DLL.
# Явно добавляем их директории в DLL search path до любых других импортов.
if hasattr(os, 'add_dll_directory') and sys.platform == 'win32':
    import site
    for _sp in site.getsitepackages():
        for _pkg in ('torch/lib', 'onnxruntime/capi'):
            _dll_dir = os.path.join(_sp, _pkg.replace('/', os.sep))
            if os.path.isdir(_dll_dir):
                os.add_dll_directory(_dll_dir)

# Windows-консоль cp1251/cp850 не поддерживает символы из метаданных Piper-моделей.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
import config
from config import (
    check_config, set_language, get_lang,
    LANGUAGE_PROFILES, LISTEN_TIMEOUT
)
import speech.STT.stt as _stt_module
from speech.STT.stt import STT, get_stt
from speech.TTS.tts_v2 import TTS
from ai.brain import Brain
from speech.STT.recorder import Recorder
from speech.STT.wake_word import wait_for_wake_word, StopListener
from utils.ramdisk import setup_vosk_ramdisk


def _set_process_priority():
    """Устанавливает приоритет процесса 'Выше среднего' через psutil."""
    try:
        import psutil
        p = psutil.Process()
        p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
        print("  [✓] Приоритет процесса: выше среднего")
    except Exception as e:
        print(f"  [~] Приоритет не изменён: {e}")

# Сколько секунд после ответа слушаем продолжение без wake word
FOLLOWUP_SECONDS = 12


def _is_stop(text: str, lang: dict) -> bool:
    """True если текст содержит команду остановки (не выход)."""
    t = text.lower()
    return any(w in t for w in lang.get("stop_words", []))


# ── Выбор языка ───────────────────────────────────────────────────────────────

def choose_language() -> str:
    print("\n  Выберите язык / Choose language:")
    for i, (code, profile) in enumerate(LANGUAGE_PROFILES.items(), 1):
        print(f"    {i}. {profile['label']} [{code}]")
    while True:
        choice = input("\n  Введите номер (Enter = русский): ").strip()
        if choice == "":
            return "ru"
        codes = list(LANGUAGE_PROFILES.keys())
        if choice.isdigit() and 1 <= int(choice) <= len(codes):
            return codes[int(choice) - 1]
        if choice.lower() in LANGUAGE_PROFILES:
            return choice.lower()
        print("  Неверный выбор, попробуйте снова.")


# ── Основной процесс одного запроса ──────────────────────────────────────────

def handle_query(stt: STT, tts: TTS, brain: Brain,
                 recorder: Recorder, lang: dict) -> str | None:
    """
    Записывает команду → распознаёт → думает → отвечает.
    Возвращает распознанный текст или None.
    """
    audio_file = recorder.record(max_seconds=LISTEN_TIMEOUT)

    if audio_file is None:
        return None

    print("  [*] Распознаю...")
    text = stt.transcribe(audio_file)

    if not text or len(text.strip()) < 2:
        print(f"  [!] {lang['not_heard']}")
        return None

    print(f"\n  Вы: {text}")
    return text


# ── Главный цикл ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗")
    print("  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝")
    print("  ██║███████║██████╔╝██║   ██║██║███████╗")
    print("  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║")
    print("  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║")
    print("  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝")
    print("=" * 55)

    if not check_config():
        sys.exit(1)

    lang_code = choose_language()
    set_language(lang_code)
    lang = get_lang()
    print(f"\n  [✓] Язык: {lang['label']}\n")

    _set_process_priority()

    print("[*] Загрузка модулей...")

    # Пробуем положить Vosk на RAM-диск перед загрузкой STT
    _stt_module.VOSK_MODEL_PATH = setup_vosk_ramdisk(_stt_module.VOSK_MODEL_PATH)

    stt      = get_stt()
    tts      = TTS()
    brain    = Brain()
    recorder = Recorder()
    recorder.calibrate()

    print(f"\n[✓] Jarvis готов!\n")
    tts.speak(lang["ready"])

    while True:
        print("=" * 55)

        # ── Шаг 1: Ждём "Jarvis" ─────────────────────────────────────────────
        wait_for_wake_word(stt=stt, tts=tts)

        # Предварительно инициализируем аудиосистему (убирает задержку в ~500ms)
        recorder.prepare()

        # Мгновенный ответ — не ждём GPT, говорим сразу
        lang = get_lang()
        tts.speak(lang["activation"])
        print(f"\n  [●] Слушаю команду... (VAD, макс {LISTEN_TIMEOUT} сек)")

        # ── Шаг 2: Основная команда ──────────────────────────────────────────
        text = handle_query(stt, tts, brain, recorder, lang)

        if text is None:
            continue

        # Проверяем выход
        # if any(w in text.lower() for w in lang["exit_words"]):
        #     tts.speak(lang["bye"])
        #     break

        # Проверяем стоп сразу после команды (до GPT)
        if _is_stop(text, lang):
            tts.speak(lang.get("stopped", "Хорошо."))
            continue

        # ── Шаг 3: GPT → TTS ─────────────────────────────────────────────────
        print(f"  [*] {lang['thinking']}")
        response = brain.think(text)
        print(f"\n  Jarvis: {response}\n")
        with StopListener(stt, tts):
            tts.speak(response)

        # ── Шаг 4: Followup — слушаем продолжение без wake word ──────────────
        followup_end = time.time() + FOLLOWUP_SECONDS

        while time.time() < followup_end:
            remaining = int(followup_end - time.time())
            print(f"\n  [👂] Продолжение диалога ({remaining} сек)... "
                  f"Говорите или скажите 'Jarvis' для новой темы")

            recorder.prepare()
            followup_text = handle_query(stt, tts, brain, recorder, lang)

            if followup_text is None:
                break

            # Стоп — прерываем followup, возвращаемся к wake word
            if _is_stop(followup_text, lang):
                tts.stop()
                break

            # Выход из Jarvis
            # if any(w in followup_text.lower() for w in lang["exit_words"]):
            #     tts.speak(lang["bye"])
            #     sys.exit(0)

            # Если сказали "Jarvis" внутри followup — просто отвечаем дальше
            if "jarvis" in followup_text.lower():
                followup_text = followup_text.lower().replace("jarvis", "").strip()
                if not followup_text:
                    tts.speak(lang["listening"])
                    recorder.prepare()
                    continue

            # Отвечаем на продолжение
            print(f"  [*] {lang['thinking']}")
            response = brain.think(followup_text)
            print(f"\n  Jarvis: {response}\n")
            with StopListener(stt, tts):
                tts.speak(response)

            # Предварительная инициализация перед следующим слушанием
            recorder.prepare()

            # Продлеваем окно followup после каждого ответа
            followup_end = time.time() + FOLLOWUP_SECONDS

        print()  # разделитель перед следующим wake word


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[*] Jarvis выключен.")