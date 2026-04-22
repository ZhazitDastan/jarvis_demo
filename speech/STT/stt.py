"""
stt.py — Speech-to-Text с автовыбором движка по языку

  Русский  → Vosk (оффлайн, быстро, не требует torch)
  Английский → faster-whisper (точнее для английского)

Модели:
  models/vosk-ru/   ← русская Vosk модель
"""

import os
import re
import wave
import json
from config import WHISPER_MODEL, get_whisper_language

VOSK_MODEL_PATH = os.path.join("models", "vosk-ru")

_HALLUCINATIONS = {
    "продолжение следует", "субтитры сделаны", "субтитры",
    "переведено", "thank you for watching", "thanks for watching",
    "amara.org", "подписывайтесь на канал", "ставьте лайки",
    "...", "…", "редактирование", "монтаж", "music", "музыка",
    ".", " ", "", "you", "the", "a",
}

_PROMPTS = {
    "ru": (
        "Голосовая команда ассистенту Jarvis. "
        "Короткая фраза или вопрос на русском. "
        "Например: открой браузер, который час, выключи компьютер."
    ),
    "en": (
        "Short voice command to Jarvis. "
        "Examples: open browser, what time is it, shut down."
    ),
}

_FAST_THRESHOLD_SEC = 3.0


class STT:
    def __init__(self):
        self._vosk_model    = None
        self._whisper_model = None
        self._load_models()

    def _load_models(self):
        lang = get_whisper_language()
        if lang == "ru":
            self._load_vosk()
            self._load_whisper(silent=True)   # тихий fallback
        else:
            self._load_whisper()

    # ── Vosk ──────────────────────────────────────────────────────────────────

    def _load_vosk(self):
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)

            if not os.path.exists(VOSK_MODEL_PATH):
                print(f"    [!] Vosk модель не найдена: {VOSK_MODEL_PATH}")
                return

            print(f"    → Загрузка Vosk...", end="", flush=True)
            self._vosk_model = Model(VOSK_MODEL_PATH)
            print(" ✓")

        except ImportError:
            print("    [!] vosk не установлен: pip install vosk")
        except Exception as e:
            print(f"    [!] Ошибка загрузки Vosk: {e}")

    # ── Whisper ───────────────────────────────────────────────────────────────

    def _load_whisper(self, silent=False):
        try:
            from faster_whisper import WhisperModel

            local_path = os.path.join("models", f"whisper-{WHISPER_MODEL}")
            model_path = local_path if os.path.exists(local_path) else WHISPER_MODEL

            if not silent:
                print(f"    → Загрузка Whisper '{model_path}'...", end="", flush=True)

            self._whisper_model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                num_workers=2,
            )
            if not silent:
                print(" ✓")

        except (ImportError, OSError) as e:
            if not silent:
                print(f"    [!] Whisper не загружен: {e}")
                print(f"    [~] Для исправления: pip install torch --index-url https://download.pytorch.org/whl/cpu")
        except Exception as e:
            if not silent:
                print(f"    [!] Ошибка загрузки Whisper: {e}")

    # ── Публичный метод ───────────────────────────────────────────────────────

    def transcribe(self, audio_path: str) -> str:
        lang = get_whisper_language()

        if lang == "ru" and self._vosk_model:
            return self._transcribe_vosk(audio_path)
        if self._whisper_model:
            return self._transcribe_whisper(audio_path)

        print("  [!] Нет доступных STT моделей")
        self._safe_delete(audio_path)
        return ""

    # ── Vosk транскрипция ─────────────────────────────────────────────────────

    def _transcribe_vosk(self, audio_path: str) -> str:
        try:
            from vosk import KaldiRecognizer

            with wave.open(audio_path, "rb") as wf:
                sample_rate = wf.getframerate()
                channels    = wf.getnchannels()
                audio_data  = wf.readframes(wf.getnframes())

            if channels > 1:
                audio_data = self._stereo_to_mono(audio_data, channels)
            if sample_rate != 16000:
                audio_data = self._resample(audio_data, sample_rate, 16000)

            rec = KaldiRecognizer(self._vosk_model, 16000)
            rec.AcceptWaveform(audio_data)

            result = json.loads(rec.FinalResult())
            text   = result.get("text", "").strip()

            if text:
                print(f"  [STT/vosk] «{text}»")
            return self._clean(text)

        except Exception as e:
            print(f"  [!] Vosk ошибка: {e}")
            if self._whisper_model:
                print("  [~] Переключаюсь на Whisper...")
                return self._transcribe_whisper(audio_path)
            return ""
        finally:
            self._safe_delete(audio_path)

    # ── Whisper транскрипция ──────────────────────────────────────────────────

    def _transcribe_whisper(self, audio_path: str) -> str:
        try:
            lang      = get_whisper_language()
            prompt    = _PROMPTS.get(lang, _PROMPTS["en"])
            duration  = self._get_duration(audio_path)
            fast_mode = duration < _FAST_THRESHOLD_SEC

            segments, info = self._whisper_model.transcribe(
                audio_path,
                language=lang,
                beam_size=1 if fast_mode else 5,
                best_of=1 if fast_mode else 5,
                temperature=0.0 if fast_mode else [0.0, 0.1, 0.2],
                condition_on_previous_text=False,
                repetition_penalty=1.2,
                log_prob_threshold=-0.8,
                no_speech_threshold=0.5,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.35,
                    min_speech_duration_ms=150,
                    min_silence_duration_ms=300,
                    speech_pad_ms=300,
                ),
                initial_prompt=prompt,
                suppress_blank=True,
            )

            parts = []
            for seg in segments:
                if seg.avg_logprob < -1.0:
                    continue
                if seg.no_speech_prob > 0.65:
                    continue
                parts.append(seg.text)

            text = self._clean(" ".join(parts))
            if text:
                mode = "fast" if fast_mode else "precise"
                print(f"  [STT/whisper-{mode}] «{text}»  "
                      f"[{info.language} {info.language_probability:.0%}]")
            return text

        except Exception as e:
            print(f"  [!] Whisper ошибка: {e}")
            return ""
        finally:
            self._safe_delete(audio_path)

    # ── Утилиты ───────────────────────────────────────────────────────────────

    def _get_duration(self, path: str) -> float:
        try:
            with wave.open(path, "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            return 5.0

    def _stereo_to_mono(self, data: bytes, channels: int) -> bytes:
        import numpy as np
        arr = np.frombuffer(data, dtype=np.int16)
        arr = arr.reshape(-1, channels)[:, 0]
        return arr.tobytes()

    def _resample(self, data: bytes, from_sr: int, to_sr: int) -> bytes:
        try:
            import numpy as np
            from scipy.signal import resample_poly
            from math import gcd
            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            g   = gcd(to_sr, from_sr)
            resampled = resample_poly(arr, to_sr // g, from_sr // g)
            return resampled.astype(np.int16).tobytes()
        except ImportError:
            return data

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[\(\[\{][^\)\]\}]{0,40}[\)\]\}]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text.lower().strip(".… !?,;:-") in _HALLUCINATIONS:
            return ""
        if len(text.strip()) < 2:
            return ""
        if re.fullmatch(r"[.\s…,!?;:\-]+", text):
            return ""
        return text

    def _safe_delete(self, path: str):
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass
