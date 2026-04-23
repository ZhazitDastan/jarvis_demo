"""
wake_word.py — детекция "Джарвис" через faster-whisper + нечёткое совпадение

Алгоритм:
  1. Непрерывно читаем микрофон маленькими кусочками (80 мс)
  2. VAD: Energy-порог определяет начало / конец речи
  3. Когда речь закончилась → транскрипция через faster-whisper (beam=1, int8)
  4. difflib.SequenceMatcher проверяет каждое слово на сходство с "джарвис"
  5. Порог совпадения 55% — ловит: "жарвис", "харвис", "jarvis", "джарвис" и т.д.
"""

import collections
import difflib
import os
import tempfile
import threading
import time
import wave

import numpy as np
import sounddevice as sd

from config import WAKE_WORD, get_whisper_language

# ── Аудио-параметры ────────────────────────────────────────────────────────────
SAMPLE_RATE     = 16000
CHUNK_SEC       = 0.08                          # размер одного кусочка
CHUNK_SIZE      = int(SAMPLE_RATE * CHUNK_SEC)

ENERGY_THRESH   = 80     # RMS-порог начала речи (снизь если mic слабый)
SILENCE_SEC     = 0.55   # секунд тишины → считаем что слово закончилось
MAX_WORD_SEC    = 3.0    # максимальная длина захватываемого сегмента
PRE_BUFFER_SEC  = 0.25   # буфер аудио до начала речи (не обрезать начало слова)
WARMUP_SEC      = 1.0    # секунд прогрева микрофона при старте

# ── Параметры нечёткого совпадения ────────────────────────────────────────────
FUZZY_THRESHOLD = 0.55   # порог SequenceMatcher (0.0–1.0)

# Цели разделены по языкам
_TARGETS_RU  = frozenset({"джарвис"})
_TARGETS_EN  = frozenset({"jarvis"})

_PHONETIC_RU = frozenset({
    "жарвис", "харвис", "карвис", "давис", "дарвис",
    "ярвис",  "шарвис", "марвис",
})
_PHONETIC_EN = frozenset({
    "garvis", "harvey", "jarbis",
})


def _wake_sets() -> tuple[frozenset, list]:
    """Возвращает (exact_set, fuzzy_list) для текущего языка."""
    if get_whisper_language() == "ru":
        exact  = _TARGETS_RU | _PHONETIC_RU | _TARGETS_EN   # EN тоже слушаем в RU режиме
        fuzzy  = list(_TARGETS_RU | _TARGETS_EN)
    else:
        exact  = _TARGETS_EN | _PHONETIC_EN                  # только EN варианты
        fuzzy  = list(_TARGETS_EN)
    return exact, fuzzy


# ── Нечёткое совпадение ───────────────────────────────────────────────────────

def _is_wake_word(text: str) -> tuple[bool, str]:
    """
    Возвращает (совпало, найденное_слово).
    В EN-режиме реагирует только на английские варианты.
    """
    if not text:
        return False, ""

    exact_set, fuzzy_list = _wake_sets()

    for word in text.lower().split():
        for target in exact_set:
            if target in word or word in target:
                return True, word

        for target in fuzzy_list:
            score = difflib.SequenceMatcher(None, word, target).ratio()
            if score >= FUZZY_THRESHOLD:
                return True, f"{word} ({score:.0%})"

    return False, ""


# ── Стоп-команда ──────────────────────────────────────────────────────────────

_STOP_TARGETS   = frozenset({"стоп", "stop"})
_STOP_PHONETIC  = frozenset({
    # RU
    "стой", "хватит", "замолчи", "тихо", "молчать", "достаточно", "стопэ",
    # EN
    "enough", "quiet", "silence", "cancel", "halt", "pause",
})
_STOP_ALL       = _STOP_TARGETS | _STOP_PHONETIC
_STOP_THRESHOLD = 0.70   # строже чем wake word — короткие слова врут чаще


def _is_stop_word(text: str) -> bool:
    if not text:
        return False
    for word in text.lower().split():
        for target in _STOP_ALL:
            if target in word or word in target:
                return True
        for target in _STOP_TARGETS:
            if difflib.SequenceMatcher(None, word, target).ratio() >= _STOP_THRESHOLD:
                return True
    return False


# ── StopListener — прерывает TTS пока он говорит ──────────────────────────────

class StopListener:
    """
    Фоновый поток, слушающий 'стоп'/'stop' пока TTS воспроизводит ответ.
    Используется как контекстный менеджер:

        with StopListener(stt, tts):
            tts.speak(response)
    """

    _CHUNK_SIZE    = int(SAMPLE_RATE * 0.08)
    _ENERGY_THRESH = 160    # выше wake word — голос должен быть громче TTS
    _SILENCE_CHUNKS = 5     # ~400 мс тишины
    _MAX_CHUNKS    = 25     # ~2 сек максимум

    def __init__(self, stt, tts):
        self._stt     = stt
        self._tts     = tts
        self._active  = threading.Event()
        self._thread  = None

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ── управление ────────────────────────────────────────────────────────────

    def start(self):
        self._active.set()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="stop-listener"
        )
        self._thread.start()

    def stop(self):
        self._active.clear()
        if self._thread:
            self._thread.join(timeout=0.3)

    # ── фоновый поток ─────────────────────────────────────────────────────────

    def _run(self):
        speech_buf: list = []
        silence_cnt = 0
        in_speech   = False

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.int16,
                blocksize=self._CHUNK_SIZE,
            ) as stream:
                while self._active.is_set():
                    chunk, _ = stream.read(self._CHUNK_SIZE)
                    chunk    = chunk.flatten()
                    energy   = float(np.abs(chunk).mean())

                    if not in_speech:
                        if energy >= self._ENERGY_THRESH:
                            in_speech   = True
                            silence_cnt = 0
                            speech_buf  = [chunk]
                    else:
                        speech_buf.append(chunk)
                        silence_cnt = silence_cnt + 1 if energy < self._ENERGY_THRESH else 0

                        ended = (
                            silence_cnt >= self._SILENCE_CHUNKS
                            or len(speech_buf) >= self._MAX_CHUNKS
                        )
                        if ended:
                            audio = np.concatenate(speech_buf)
                            text  = _transcribe_fast(self._stt, audio)
                            if text:
                                print(f"  [stop?] «{text}»")
                            if _is_stop_word(text):
                                print("  [✓] Прерывание речи!")
                                self._tts.stop()
                                self._active.clear()
                                return
                            speech_buf.clear()
                            in_speech   = False
                            silence_cnt = 0
        except Exception:
            pass   # поток завершается вместе с TTS


# ── Транскрипция ──────────────────────────────────────────────────────────────

def _save_wav(audio: np.ndarray) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = tmp.name
    tmp.close()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.astype(np.int16).tobytes())
    return path


def _transcribe_fast(stt, audio: np.ndarray) -> str:
    """
    Выбирает движок по активному языку:
      ru  → Vosk   (быстро, оффлайн, без torch)
      en  → faster-whisper (beam=1, greedy)
    """
    if get_whisper_language() == "ru":
        return _transcribe_vosk(stt, audio)
    return _transcribe_whisper(stt, audio)


def _transcribe_vosk(stt, audio: np.ndarray) -> str:
    """Транскрипция через Vosk — для русского wake word."""
    vosk_model = getattr(stt, "_vosk_model", None)
    if vosk_model is None:
        print("  [!] Vosk модель не загружена")
        return ""
    try:
        import json
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
        rec.AcceptWaveform(audio.astype(np.int16).tobytes())
        result = json.loads(rec.FinalResult())
        return result.get("text", "").strip()
    except Exception as e:
        print(f"  [!] wake vosk: {e}")
        return ""


def _transcribe_whisper(stt, audio: np.ndarray) -> str:
    """Транскрипция через faster-whisper — для английского wake word."""
    whisper = getattr(stt, "_whisper_model", None)
    if whisper is None:
        print("  [!] Whisper модель не загружена")
        return ""
    path = _save_wav(audio)
    try:
        segments, _ = whisper.transcribe(
            path,
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            suppress_blank=True,
            no_speech_threshold=0.65,
            log_prob_threshold=-1.5,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.35,
                min_speech_duration_ms=80,
                min_silence_duration_ms=150,
            ),
        )
        return " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        print(f"  [!] wake whisper: {e}")
        return ""
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── Основная функция ──────────────────────────────────────────────────────────

def wait_for_wake_word(stt, tts=None, timeout: int = 0) -> bool:
    """
    Ждёт слово активации через faster-whisper + нечёткое совпадение.
    Возвращает True при активации, False при таймауте.

    stt     — экземпляр STT (нужен _whisper_model или _vosk_model)
    tts     — экземпляр TTS (чтобы не слушать пока говорит Jarvis)
    timeout — секунд ожидания (0 = бесконечно)
    """
    engine = "vosk" if get_whisper_language() == "ru" else "faster-whisper"
    print(f"\n  [👂] Жду '{WAKE_WORD}' ({engine} + fuzzy match)...")

    pad_chunks     = max(1, int(PRE_BUFFER_SEC / CHUNK_SEC))
    silence_chunks = max(1, int(SILENCE_SEC    / CHUNK_SEC))
    max_chunks     = max(1, int(MAX_WORD_SEC   / CHUNK_SEC))

    pre_buffer: collections.deque = collections.deque(maxlen=pad_chunks)
    speech_buffer: list            = []
    silence_count  = 0
    in_speech      = False
    start_time     = time.time()
    warmup_end     = start_time + WARMUP_SEC

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
        blocksize=CHUNK_SIZE,
    ) as stream:

        while True:
            # ── Таймаут ───────────────────────────────────────────────────────
            if timeout > 0 and (time.time() - start_time) > timeout:
                return False

            # ── Пока TTS говорит — не слушаем, сбрасываем буфер ──────────────
            if tts and getattr(tts.__class__, "is_speaking", False):
                stream.read(CHUNK_SIZE)
                pre_buffer.clear()
                speech_buffer.clear()
                in_speech     = False
                silence_count = 0
                continue

            chunk, _ = stream.read(CHUNK_SIZE)
            chunk     = chunk.flatten()
            energy    = float(np.abs(chunk).mean())

            # ── Прогрев: игнорируем первый WARMUP_SEC ────────────────────────
            if time.time() < warmup_end:
                pre_buffer.append(chunk)
                continue

            # ── VAD: детекция начала речи ─────────────────────────────────────
            if not in_speech:
                pre_buffer.append(chunk)
                if energy >= ENERGY_THRESH:
                    in_speech     = True
                    silence_count = 0
                    speech_buffer = list(pre_buffer)   # берём пред-буфер
                    speech_buffer.append(chunk)

            # ── VAD: идёт речь ────────────────────────────────────────────────
            else:
                speech_buffer.append(chunk)

                if energy < ENERGY_THRESH:
                    silence_count += 1
                else:
                    silence_count = 0

                word_ended = (
                    silence_count >= silence_chunks
                    or len(speech_buffer) >= max_chunks
                )

                if word_ended:
                    audio = np.concatenate(speech_buffer)
                    text  = _transcribe_fast(stt, audio)

                    if text:
                        print(f"  [~] «{text}»")

                    matched, match_word = _is_wake_word(text)
                    if matched:
                        print(f"  [✓] Активация!  ← «{match_word}»")
                        return True

                    # Сброс для следующего слова
                    pre_buffer.clear()
                    speech_buffer.clear()
                    in_speech     = False
                    silence_count = 0