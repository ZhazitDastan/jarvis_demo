"""
tts_v2.py — Text-to-Speech через Piper (локально, оффлайн, быстро)

Почему Piper лучше edge-tts:
  - Полностью оффлайн — не нужен интернет
  - Быстрее — генерация прямо в памяти без сетевых запросов
  - Нет задержки на соединение с сервером Microsoft

Установка:
  pip install piper-tts

Скачать голосовые модели (нужны два файла — .onnx и .onnx.json):

  Русский (мужской):
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json

  Английский (мужской):
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json

  Положи оба файла в папку: models/voices/

Использование в main.py:
  from tts_v2 import TTS       # просто замени импорт
  API идентичен tts.py — speak(), speak_activation(), preload(), stop()
"""

import io
import os
import queue
import re
import time
import wave
import random
import threading
import collections
import numpy as np
import sounddevice as sd
import config
from config import get_lang


def _split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения для конвейерного синтеза."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

# ── Фразы активации ───────────────────────────────────────────────────────────
_ACTIVATION_RU = [
    "Да, сэр?",
    "Слушаю.",
    "К вашим услугам.",
    "Чем могу помочь?",
    "Готов.",
    "На связи.",
    "Всегда готов.",
    "Жду команды.",
    "Слушаю вас.",
    "Здесь, сэр.",
]

_ACTIVATION_EN = [
    "Yes, sir?",
    "Listening.",
    "At your service.",
    "How can I help?",
    "Ready.",
    "Online.",
    "Standing by.",
    "Awaiting your command.",
    "Here, sir.",
    "Go ahead.",
]

# ── Настройки ─────────────────────────────────────────────────────────────────
VOICES_DIR    = "models/voices"   # папка с .onnx и .onnx.json файлами
CACHE_SIZE    = 50                # максимум фраз в LRU кэше
ECHO_PAUSE    = 0.2               # секунд паузы после речи (эхо)
LENGTH_SCALE  = 0.9               # скорость речи (< 1.0 = быстрее, > 1.0 = медленнее)
NOISE_SCALE   = 0.1               # вариативность голоса
NOISE_W       = 0.1               # вариативность темпа

# Настройки по умолчанию для каждого языка.
# Английская модель ожидает noise_scale=0.667, noise_w=0.8 — именно эти значения
# задают естественную интонацию. При 0.1 голос звучит монотонно и плоско.
# Английский также звучит естественнее на скорости 1.0, а не 0.9.
_LANG_DEFAULTS = {
    "ru": {"length_scale": 0.9,  "noise_scale": 0.1,   "noise_w": 0.1},
    "en": {"length_scale": 1.0,  "noise_scale": 0.667,  "noise_w": 0.8},
}

# Пути к моделям голосов.
# Для английского en_US-lessac-high звучит естественнее чем ryan-high —
# можно заменить, скачав модель с того же HuggingFace репозитория.
VOICE_MODELS = {
    "ru": os.path.join(VOICES_DIR, "ru_RU-ruslan-medium.onnx"),
    "en": os.path.join(VOICES_DIR, "en_US-ryan-high.onnx"),
}


class TTS:
    is_speaking: bool = False

    def __init__(self):
        self._voice    = None        # загруженная модель Piper
        self._lang     = None        # текущий язык
        self._sr       = 22050       # sample rate (зависит от модели)
        self._lock     = threading.Lock()
        self._stop_evt = threading.Event()

        # LRU кэш: текст → numpy array с аудио
        self._cache: collections.OrderedDict[str, np.ndarray] = \
            collections.OrderedDict()

        self._load_voice()
        if self._voice:
            print("    ✓ TTS v2 (Piper) готов")
        else:
            print("    ⚠ TTS v2 (Piper) не загружен — используется текстовый режим")

    # ── Загрузка модели ───────────────────────────────────────────────────────

    def _load_voice(self):
        """Загружает голосовую модель Piper для текущего языка с подробной диагностикой."""
        try:
            from piper.voice import PiperVoice

            lang_code  = config.ACTIVE_LANGUAGE
            model_path = VOICE_MODELS.get(lang_code)

            # ── Валидация пути ──
            if not model_path:
                print(f"\n  [!] Неизвестный язык: {lang_code}")
                self._voice = None
                return

            # ── Проверка существования файлов ──
            if not os.path.exists(model_path):
                # Проверяем какой файл отсутствует
                onnx_file = model_path
                json_file = model_path + ".json"

                print(f"\n  [!] Модель Piper не найдена для языка '{lang_code}':")
                print(f"      Ожидалась: {onnx_file}")

                if not os.path.exists(onnx_file):
                    print(f"      ❌ Отсутствует: {os.path.basename(onnx_file)}")
                if not os.path.exists(json_file):
                    print(f"      ❌ Отсутствует: {os.path.basename(json_file)}")

                print(f"\n  [📥] Скачай модель (оба файла!):")
                if lang_code == "ru":
                    print(f"      wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx -O {onnx_file}")
                    print(f"      wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json -O {json_file}")
                else:
                    print(f"      wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx -O {onnx_file}")
                    print(f"      wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json -O {json_file}")

                print(f"\n  [📁] Или положи в папку вручную: {os.path.abspath(VOICES_DIR)}/")
                self._voice = None
                return

            # ── Загрузка модели ──
            print(f"    → Загрузка Piper модели ({os.path.basename(model_path)})...",
                  end="", flush=True)

            self._voice   = PiperVoice.load(model_path)
            self._lang    = lang_code

            # Определяем sample rate из модели
            if hasattr(self._voice, "config"):
                self._sr = self._voice.config.sample_rate

            # Применяем языковые настройки по умолчанию
            global LENGTH_SCALE, NOISE_SCALE, NOISE_W
            defaults = _LANG_DEFAULTS.get(lang_code, _LANG_DEFAULTS["en"])
            LENGTH_SCALE = defaults["length_scale"]
            NOISE_SCALE  = defaults["noise_scale"]
            NOISE_W      = defaults["noise_w"]

            print(f" ✓ (sr={self._sr}, speed={LENGTH_SCALE})")

        except ImportError as e:
            print(f"\n  [!] piper-tts не установлен или отсутствует зависимость:")
            print(f"      pip install piper-tts")
            print(f"      Ошибка: {e}")
            self._voice = None
        except Exception as e:
            print(f"\n  [!] Критическая ошибка при загрузке Piper:")
            print(f"      {type(e).__name__}: {e}")
            import traceback
            print("\n  [DEBUG] Трассировка:")
            traceback.print_exc()
            self._voice = None

    # ── Предзагрузка ──────────────────────────────────────────────────────────

    def preload(self):
        """Генерирует системные фразы заранее и кладёт в кэш."""
        if not self._voice:
            print("  [⚠] Piper не загружен — preload пропущен")
            print("  [~] Убедись что модели скачаны и положены в models/voices/")
            return

        act     = _ACTIVATION_RU if config.ACTIVE_LANGUAGE == "ru" else _ACTIVATION_EN
        system  = [
            lang.get("ready", ""),
            lang.get("listening", ""),
            lang.get("not_heard", ""),
            lang.get("bye", ""),
        ]
        phrases = [p for p in act + system if p]

        print(f"    → Предзагрузка {len(phrases)} фраз (Piper)...",
              end="", flush=True)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        results: dict[str, np.ndarray] = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(self._synthesize, p): p for p in phrases}
            for future in as_completed(futures):
                phrase = futures[future]
                try:
                    audio  = future.result()
                    if audio is not None:
                        results[phrase] = audio
                except Exception as e:
                    print(f"\n  [!] Ошибка синтеза фразы '{phrase}': {e}")

        for phrase, audio in results.items():
            self._add_cache(phrase, audio)

        print(f" ✓ ({len(self._cache)} в кэше)")

    # ── Публичные методы ──────────────────────────────────────────────────────

    def speak(self, text: str):
        """Озвучивает текст локально через Piper. Блокирует до конца."""
        if not text or not text.strip():
            return

        if not self._voice:
            print(f"  [TTS] {text}")
            return

        self._stop_evt.clear()

        sentences = _split_sentences(text)

        # Одно предложение — синтез и воспроизведение без конвейера
        if len(sentences) <= 1:
            try:
                audio = self._get_cache(text)
                if audio is None:
                    audio = self._synthesize(text)
                    if audio is None:
                        return
                    self._add_cache(text, audio)
                TTS.is_speaking = True
                try:
                    self._play(audio)
                finally:
                    time.sleep(ECHO_PAUSE)
                    TTS.is_speaking = False
            except Exception as e:
                TTS.is_speaking = False
                print(f"  [!] TTS v2 ошибка: {e}")
            return

        # Несколько предложений — конвейер: синтез следующего пока играет текущее.
        # Очередь с буфером 2: продюсер всегда на шаг впереди плеера.
        audio_q: queue.Queue = queue.Queue(maxsize=2)

        def _producer():
            for s in sentences:
                if self._stop_evt.is_set():
                    break
                a = self._get_cache(s)
                if a is None:
                    a = self._synthesize(s)
                    if a is not None:
                        self._add_cache(s, a)
                audio_q.put(a)
            audio_q.put(None)  # сигнал окончания

        threading.Thread(target=_producer, daemon=True, name="tts-producer").start()

        TTS.is_speaking = True
        try:
            while True:
                a = audio_q.get()
                if a is None or self._stop_evt.is_set():
                    break
                self._play(a)
        finally:
            time.sleep(ECHO_PAUSE)
            TTS.is_speaking = False

    def speak_activation(self):
        """Случайная фраза активации — мгновенно из кэша."""
        phrases = _ACTIVATION_RU if config.ACTIVE_LANGUAGE == "ru" else _ACTIVATION_EN

        # Не повторять предыдущую фразу
        if hasattr(self, "_last_act"):
            choices = [p for p in phrases if p != self._last_act]
            phrase  = random.choice(choices if choices else phrases)
        else:
            phrase = random.choice(phrases)

        self._last_act = phrase
        self.speak(phrase)

    def stop(self):
        """Прерывает текущее воспроизведение."""
        self._stop_evt.set()
        sd.stop()
        TTS.is_speaking = False

    # ── Синтез через Piper ────────────────────────────────────────────────────

    def _synthesize(self, text: str) -> np.ndarray | None:
        """
        Синтезирует текст в numpy array с аудио данными.
        Всё происходит локально — нет сетевых запросов.
        """
        try:
            from piper import SynthesisConfig

            syn_config = SynthesisConfig(
                length_scale=LENGTH_SCALE,
                noise_scale=NOISE_SCALE,
                noise_w_scale=NOISE_W,
                normalize_audio=True,
            )

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._sr)
                self._voice.synthesize_wav(text, wf, syn_config=syn_config)

            buf.seek(0)
            with wave.open(buf, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio  = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                audio  = audio / 32768.0

            return audio

        except ImportError:
            # Старый API без SynthesisConfig
            try:
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self._sr)
                    self._voice.synthesize_wav(text, wf)

                buf.seek(0)
                with wave.open(buf, "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    audio  = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                    audio  = audio / 32768.0
                return audio
            except Exception as e:
                print(f"  [!] Piper синтез (fallback): {e}")
                return None

        except Exception as e:
            print(f"  [!] Piper синтез: {e}")
            return None

    # ── Воспроизведение ───────────────────────────────────────────────────────

    def _play(self, audio: np.ndarray):
        """Воспроизводит numpy массив через sounddevice с поддержкой стопа."""
        try:
            sd.play(audio, samplerate=self._sr, blocking=False)
            # Ждём по длине аудио — sd.get_stream() не работает вне OutputStream context
            duration = len(audio) / self._sr
            deadline = time.time() + duration + 0.3
            while time.time() < deadline:
                if self._stop_evt.is_set():
                    sd.stop()
                    return
                time.sleep(0.02)
        except Exception as e:
            print(f"  [!] Воспроизведение: {e}")

    # ── LRU кэш ───────────────────────────────────────────────────────────────

    def _add_cache(self, text: str, audio: np.ndarray):
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
            else:
                if len(self._cache) >= CACHE_SIZE:
                    self._cache.popitem(last=False)   # удаляем самый старый
                self._cache[text] = audio

    def _get_cache(self, text: str) -> np.ndarray | None:
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
        return None

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def __del__(self):
        self.clear_cache()