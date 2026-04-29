"""
tts_v3.py — Text-to-Speech через Microsoft Edge TTS (бесплатно, нейронный голос)

Голоса:
  RU → ru-RU-DmitryNeural   (мужской, естественный)
  EN → en-GB-RyanNeural     (британский мужской — идеально для Jarvis)

Требует: edge-tts, av (PyAV — уже в requirements, бандлит ffmpeg)
Интернет: нужен (Microsoft Azure Neural TTS)
Скорость: ~200-400 мс (быстрее OpenAI TTS в 2-3 раза)
"""

import asyncio
import collections
import io
import random
import threading
import time

import av
import numpy as np
import sounddevice as sd

import config
from config import get_lang


# ── Постоянный фоновый event loop для Edge TTS ────────────────────────────────
# Создание нового event loop на каждый speak() стоит 50-100мс.
# Один общий loop в фоновом потоке убирает эти накладные расходы.

_bg_loop: asyncio.AbstractEventLoop | None = None
_bg_loop_lock = threading.Lock()


def _get_bg_loop() -> asyncio.AbstractEventLoop:
    global _bg_loop
    if _bg_loop is not None and not _bg_loop.is_closed():
        return _bg_loop
    with _bg_loop_lock:
        if _bg_loop is not None and not _bg_loop.is_closed():
            return _bg_loop
        loop = asyncio.new_event_loop()
        t = threading.Thread(
            target=loop.run_forever,
            daemon=True,
            name="tts-loop",
        )
        t.start()
        _bg_loop = loop
        return loop

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

# ── Голоса по умолчанию (если не заданы в config) ─────────────────────────────

_DEFAULT_VOICES = {
    "ru": "ru-RU-DmitryNeural",
    "en": "en-GB-RyanNeural",
}
_DEFAULT_RATES = {
    "ru": "+15%",
    "en": "+15%",
}

ECHO_PAUSE   = 0.05   # пауза после речи (уменьшено, эхо минимально на Edge TTS)
CACHE_SIZE   = 60     # LRU кэш фраз
LENGTH_SCALE = 1.0    # заглушка для совместимости с /settings


def _get_voice() -> str:
    lang = getattr(config, "ACTIVE_LANGUAGE", "ru")
    return config.LANGUAGE_PROFILES.get(lang, {}).get("tts_voice") \
           or _DEFAULT_VOICES.get(lang, "en-GB-RyanNeural")


def _get_rate() -> str:
    lang = getattr(config, "ACTIVE_LANGUAGE", "ru")
    return config.LANGUAGE_PROFILES.get(lang, {}).get("tts_rate") \
           or _DEFAULT_RATES.get(lang, "+15%")


# ── Декодинг MP3 → numpy ──────────────────────────────────────────────────────

def _mp3_to_numpy(mp3_bytes: bytes) -> tuple[np.ndarray, int]:
    """Декодирует MP3 байты в float32 numpy массив через PyAV."""
    with av.open(io.BytesIO(mp3_bytes)) as container:
        stream = container.streams.audio[0]
        sr     = stream.codec_context.sample_rate
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=sr)
        chunks = []
        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                chunks.append(rf.to_ndarray()[0])
    audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)
    return audio, sr


# ── Синтез через Edge TTS ─────────────────────────────────────────────────────

async def _synth_async(text: str, voice: str, rate: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    mp3 = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3 += chunk["data"]
    return mp3


def _synthesize(text: str, voice: str, rate: str) -> tuple[np.ndarray, int] | None:
    """Запускает async синтез в общем фоновом event loop (быстро)."""
    try:
        loop = _get_bg_loop()
        future = asyncio.run_coroutine_threadsafe(
            _synth_async(text, voice, rate), loop
        )
        mp3 = future.result(timeout=15.0)
        if not mp3:
            return None
        return _mp3_to_numpy(mp3)

    except Exception as e:
        print(f"  [!] TTS v3 синтез: {e}")
        return None


# ── Класс TTS ─────────────────────────────────────────────────────────────────

class TTS:
    is_speaking: bool = False

    def __init__(self):
        self._lock     = threading.Lock()
        self._stop_evt = threading.Event()
        self._cache: collections.OrderedDict[str, tuple[np.ndarray, int]] = \
            collections.OrderedDict()
        self._warmup_audio_device()
        _get_bg_loop()   # запускаем фоновый event loop заранее
        print("    ✓ TTS v3 (Edge TTS) готов")

    def _warmup_audio_device(self):
        """Предварительно инициализирует звуковое устройство."""
        try:
            sd.play(np.zeros(1000, dtype=np.float32), samplerate=16000, blocking=False)
            sd.stop()
        except Exception:
            pass

    # ── Предзагрузка ──────────────────────────────────────────────────────────

    def preload(self):
        """Синтезирует фразы активации заранее и кладёт в LRU кэш."""
        lang    = getattr(config, "ACTIVE_LANGUAGE", "ru")
        phrases = _ACTIVATION_RU if lang == "ru" else _ACTIVATION_EN
        system  = [
            get_lang().get("ready", ""),
            get_lang().get("listening", ""),
            get_lang().get("not_heard", ""),
            get_lang().get("bye", ""),
        ]
        to_load = [p for p in phrases + system if p]

        print(f"    → Предзагрузка {len(to_load)} фраз (Edge TTS)...",
              end="", flush=True)

        voice = _get_voice()
        rate  = _get_rate()

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_synthesize, p, voice, rate): p for p in to_load}
            for future in as_completed(futures):
                phrase = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        self._cache_put(phrase, result)
                except Exception as e:
                    print(f"\n  [!] preload '{phrase}': {e}")

        print(f" ✓ ({len(self._cache)} в кэше)")

    # ── Публичные методы ──────────────────────────────────────────────────────

    def speak(self, text: str):
        """Озвучивает текст через Edge TTS. Блокирует до конца воспроизведения."""
        if not text or not text.strip():
            return

        self._stop_evt.clear()

        try:
            voice = _get_voice()
            rate  = _get_rate()

            result = self._cache_get(text)
            if result is None:
                result = _synthesize(text, voice, rate)
                if result is None:
                    print(f"  [TTS] {text}")
                    return
                self._cache_put(text, result)

            audio, sr = result
            TTS.is_speaking = True
            try:
                self._play(audio, sr)
            finally:
                time.sleep(ECHO_PAUSE)
                TTS.is_speaking = False

        except Exception as e:
            TTS.is_speaking = False
            print(f"  [!] TTS v3 ошибка: {e}")

    def speak_activation(self):
        """Случайная фраза активации — мгновенно из кэша."""
        lang    = getattr(config, "ACTIVE_LANGUAGE", "ru")
        phrases = _ACTIVATION_RU if lang == "ru" else _ACTIVATION_EN

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

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    # ── Воспроизведение ───────────────────────────────────────────────────────

    def _play(self, audio: np.ndarray, sr: int):
        try:
            sd.play(audio, samplerate=sr, blocking=False)
            duration = len(audio) / sr
            # Event.wait() блокируется без CPU-нагрузки и просыпается мгновенно при stop
            interrupted = self._stop_evt.wait(timeout=duration)
            if interrupted:
                sd.stop()
        except Exception as e:
            print(f"  [!] TTS воспроизведение: {e}")

    # ── LRU кэш ───────────────────────────────────────────────────────────────

    def _cache_put(self, text: str, value: tuple[np.ndarray, int]):
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
            else:
                if len(self._cache) >= CACHE_SIZE:
                    self._cache.popitem(last=False)
                self._cache[text] = value

    def _cache_get(self, text: str) -> tuple[np.ndarray, int] | None:
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
        return None

    def __del__(self):
        self.clear_cache()
