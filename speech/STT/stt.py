"""
stt.py — Speech-to-Text с автовыбором движка по языку

  RU / EN  → OpenAI Whisper API (основной, точный)
  RU       → Vosk RU (оффлайн fallback + wake word)
  EN       → Vosk EN (оффлайн fallback + wake word)

Модели:
  models/vosk-model-small-ru-0.22/        ← русская Vosk модель
  models/vosk-model-en-us-0.22-lgraph/    ← английская Vosk модель
"""

import os
import re
import wave
import json
from config import VOSK_MODEL_DIR, VOSK_EN_MODEL_DIR, get_whisper_language, OPENAI_API_KEY

VOSK_MODEL_PATH    = VOSK_MODEL_DIR
VOSK_EN_MODEL_PATH = VOSK_EN_MODEL_DIR

_instance: 'STT | None' = None


def get_stt() -> 'STT':
    """Возвращает единственный экземпляр STT — модели загружаются один раз."""
    global _instance
    if _instance is None:
        _instance = STT()
    return _instance

_HALLUCINATIONS = {
    "продолжение следует", "субтитры сделаны", "субтитры",
    "переведено", "thank you for watching", "thanks for watching",
    "amara.org", "подписывайтесь на канал", "ставьте лайки",
    "...", "…", "редактирование", "монтаж", "music", "музыка",
    ".", " ", "", "you", "the", "a",
}

# Фразы-триггеры галлюцинаций Whisper (начало зацикленного текста)
# Только фразы которые НИКОГДА не бывают реальными командами
_HALLUCINATION_STARTS = {
    "продолжение следует", "это приходит",
    "это то что", "субтитры", "редактор субтитров",
}


def _is_repetitive(text: str, max_repeat: int = 3) -> bool:
    """
    Детектирует зацикленный текст типа "It comes ! It comes ! It comes !".
    Возвращает True если одна фраза (1-4 слова) встречается >= max_repeat раз.
    """
    words = text.lower().split()
    if len(words) < max_repeat * 2:
        return False
    # n=1 пропускаем: служебные слова (the, and, is) повторяются в нормальной речи
    for n in range(2, 5):
        if len(words) < n:
            break
        ngrams = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
        for gram in set(ngrams):
            if ngrams.count(gram) >= max_repeat:
                return True
    return False

_PROMPTS = {
    # НЕ давай примеры команд — Whisper галлюцинирует их на тишине/шуме.
    # Нейтральный стиль-промпт без конкретных фраз.
    "ru": "Голосовая команда на русском языке.",
    "en": "Short voice command in English.",
}



def _detect_lang(text: str) -> str:
    """Определяет язык по доле кириллицы в тексте: 'ru' или 'en'."""
    if not text:
        return "?"
    cyrillic = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    return "ru" if cyrillic / max(len(text), 1) > 0.25 else "en"


class STT:
    def __init__(self):
        self._vosk_model    = None   # Vosk RU
        self._vosk_model_en = None   # Vosk EN
        self._load_models()

    def _load_models(self):
        self._load_vosk_ru()
        self._load_vosk_en()

    # ── Vosk RU ───────────────────────────────────────────────────────────────

    def _load_vosk_ru(self):
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            if not os.path.exists(VOSK_MODEL_PATH):
                print(f"    [!] Vosk RU модель не найдена: {VOSK_MODEL_PATH}")
                return
            print(f"    → Загрузка Vosk RU...", end="", flush=True)
            self._vosk_model = Model(VOSK_MODEL_PATH)
            print(" ✓")
        except ImportError:
            print("    [!] vosk не установлен: pip install vosk")
        except Exception as e:
            print(f"    [!] Ошибка загрузки Vosk RU: {e}")

    # ── Vosk EN ───────────────────────────────────────────────────────────────

    def _load_vosk_en(self):
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            if not os.path.exists(VOSK_EN_MODEL_PATH):
                print(f"    [!] Vosk EN модель не найдена: {VOSK_EN_MODEL_PATH}")
                return
            print(f"    → Загрузка Vosk EN...", end="", flush=True)
            self._vosk_model_en = Model(VOSK_EN_MODEL_PATH)
            print(" ✓")
        except ImportError:
            pass   # vosk уже проверен в _load_vosk_ru
        except Exception as e:
            print(f"    [!] Ошибка загрузки Vosk EN: {e}")

    # ── Публичный метод ───────────────────────────────────────────────────────

    def transcribe(self, audio_path: str) -> str:
        if OPENAI_API_KEY:
            return self._transcribe_openai(audio_path)

        # Fallback на Vosk если нет ключа
        lang = get_whisper_language()
        if lang == "ru" and self._vosk_model:
            return self._transcribe_vosk(audio_path)
        if self._vosk_model_en:
            return self._transcribe_vosk_en(audio_path)

        print("  [!] Нет OpenAI ключа и Vosk моделей")
        self._safe_delete(audio_path)
        return ""

    # ── OpenAI Whisper API ────────────────────────────────────────────────────

    def _transcribe_openai(self, audio_path: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            lang   = get_whisper_language()

            with open(audio_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    # language не указываем → Whisper сам определяет RU/EN по речи
                    prompt=_PROMPTS.get(lang, _PROMPTS["en"]),
                    timeout=8.0,
                )

            text = self._clean(result.text.strip())
            if text:
                detected = _detect_lang(text)
                print(f"  [STT/openai] «{text}» [{detected}]")
            return text

        except Exception as e:
            print(f"  [!] OpenAI Whisper error / ошибка: {e}")
            lang = get_whisper_language()
            if lang == "ru" and self._vosk_model:
                return self._transcribe_vosk(audio_path)
            if self._vosk_model_en:
                return self._transcribe_vosk_en(audio_path)
            return ""
        finally:
            self._safe_delete(audio_path)

    # ── Vosk RU транскрипция ──────────────────────────────────────────────────

    def _transcribe_vosk(self, audio_path: str) -> str:
        return self._transcribe_vosk_model(audio_path, self._vosk_model, "ru")

    # ── Vosk EN транскрипция ──────────────────────────────────────────────────

    def _transcribe_vosk_en(self, audio_path: str) -> str:
        return self._transcribe_vosk_model(audio_path, self._vosk_model_en, "en")

    def _transcribe_vosk_model(self, audio_path: str, model, lang_tag: str) -> str:
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

            rec = KaldiRecognizer(model, 16000)
            rec.AcceptWaveform(audio_data)

            result = json.loads(rec.FinalResult())
            text   = result.get("text", "").strip()

            if text:
                print(f"  [STT/vosk] «{text}» [{lang_tag}]")
            return self._clean(text)

        except Exception as e:
            print(f"  [!] Vosk error / ошибка: {e}")
            return ""
        finally:
            self._safe_delete(audio_path)

    # ── Утилиты ───────────────────────────────────────────────────────────────


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
        lower = text.lower().strip(".… !?,;:-")
        if lower in _HALLUCINATIONS:
            print(f"  [STT] отброшено (галлюцинация): «{text}»")
            return ""
        if len(text.strip()) < 2:
            print(f"  [STT] отброшено (слишком коротко): «{text}»")
            return ""
        if re.fullmatch(r"[.\s…,!?;:\-]+", text):
            print(f"  [STT] отброшено (только знаки): «{text}»")
            return ""
        if _is_repetitive(text):
            print(f"  [STT] отброшено (повторяющийся текст): «{text}»")
            return ""
        for start in _HALLUCINATION_STARTS:
            if lower.startswith(start):
                print(f"  [STT] отброшено (триггер «{start}»): «{text}»")
                return ""
        return text

    def _safe_delete(self, path: str):
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass
