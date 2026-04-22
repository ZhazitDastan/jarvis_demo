"""
stt.py — Speech-to-Text через faster-whisper

Настройки для проблемы "слова перепутаны":
  - condition_on_previous_text=False  — не зависит от предыдущего распознавания
  - repetition_penalty               — штрафует повторяющиеся слова
  - word_timestamps                  — детектирует границы слов точнее
  - Фильтрация галлюцинаций и низкоуверенных сегментов
"""

import os
import re
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, get_whisper_language

# Галлюцинации — мусор который Whisper генерирует на тишине/шуме
_HALLUCINATIONS = {
    "продолжение следует", "субтитры сделаны", "субтитры",
    "переведено", "thank you for watching", "thanks for watching",
    "amara.org", "подписывайтесь на канал", "ставьте лайки",
    "...", "…", "редактирование", "монтаж",
}

_PROMPT_RU = (
    "Голосовая команда ассистенту Jarvis. "
    "Короткие фразы и вопросы на русском языке. "
    "Например: открой браузер, который час, включи музыку."
)
_PROMPT_EN = (
    "Voice command to Jarvis assistant. "
    "Short phrases and questions in English."
)


class STT:
    def __init__(self):
        print(f"    → Загрузка Whisper '{WHISPER_MODEL}'...")
        self.model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            num_workers=1,
        )
        self._prompt = _PROMPT_RU if get_whisper_language() == "ru" else _PROMPT_EN
        print("    ✓ Whisper готов")

    def transcribe(self, audio_path: str) -> str:
        try:
            segments, info = self.model.transcribe(
                audio_path,
                language=get_whisper_language(),

                # ── Качество ──────────────────────────────────────────────────
                beam_size=5,
                best_of=5,             # больше кандидатов → меньше перепутанных слов

                # ── Борьба с перепутанными словами ────────────────────────────
                # Не переносить контекст из предыдущего сегмента — главная причина путаницы
                condition_on_previous_text=False,
                # Штраф за повторение одного слова подряд
                repetition_penalty=1.2,
                # Температура: пробуем детерминированный вариант первым,
                # если плохо — чуть добавляем вариативность
                temperature=[0.0, 0.1, 0.2],

                # ── Фильтры уверенности ───────────────────────────────────────
                log_prob_threshold=-0.7,    # отсекаем неуверенные сегменты
                no_speech_threshold=0.45,   # отсекаем тишину

                # ── VAD внутри Whisper ────────────────────────────────────────
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.35,
                    min_speech_duration_ms=150,
                    min_silence_duration_ms=300,
                    speech_pad_ms=300,
                ),

                # ── Контекст ─────────────────────────────────────────────────
                initial_prompt=self._prompt,
                suppress_blank=True,
            )

            parts = []
            for seg in segments:
                # Пропускаем сегменты с низкой уверенностью
                if seg.avg_logprob < -1.0:
                    continue
                if seg.no_speech_prob > 0.65:
                    continue
                parts.append(seg.text)

            text = self._clean(" ".join(parts))

            if text:
                print(f"  [STT] «{text}»  "
                      f"[lang={info.language} "
                      f"p={info.language_probability:.0%}]")
            return text

        except Exception as e:
            print(f"  [!] Ошибка STT: {e}")
            return ""
        finally:
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        # Убираем аннотации: (музыка), [смех]
        text = re.sub(r"[\(\[\{][^\)\]\}]{0,40}[\)\]\}]", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        if text.lower().strip(".… ") in _HALLUCINATIONS:
            return ""
        if len(text) < 3:
            return ""
        if re.fullmatch(r"[.\s…,!?;:\-]+", text):
            return ""
        return text
