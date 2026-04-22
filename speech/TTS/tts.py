"""
tts.py — Text-to-Speech с оптимизациями скорости

Улучшения:
  1. Предгенерация частых фраз при старте (нет задержки на "Да, сэр")
  2. Скорость речи +20% — убирает длинные паузы
  3. Случайные фразы активации в стиле Jarvis
  4. is_speaking флаг для защиты от эха
"""

import asyncio
import tempfile
import os
import time
import random
import threading
import edge_tts
import pygame
from config import get_lang

# ── Фразы активации в стиле Jarvis ───────────────────────────────────────────
_ACTIVATION_RU = [
    "Да, сэр?",
    "Слушаю.",
    "К вашим услугам.",
    "Чем могу помочь?",
    "Готов.",
    "На связи.",
    "Всегда к вашим услугам.",
    "Жду команды.",
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
]


class TTS:
    is_speaking: bool = False

    def __init__(self):
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
        self._cache: dict[str, str] = {}
        print("    ✓ TTS готов")

    def preload(self):
        """
        Предгенерирует частые фразы при старте.
        После этого speak() для них работает мгновенно — без задержки генерации.
        """
        lang    = get_lang()
        phrases = _ACTIVATION_RU if lang["label"] == "Русский" else _ACTIVATION_EN
        extras  = [lang.get("ready", ""), lang.get("listening", ""),
                   lang.get("not_heard", ""), lang.get("bye", "")]
        all_phrases = [p for p in phrases + extras if p]

        print(f"    → Предгенерация {len(all_phrases)} фраз...", end="", flush=True)
        asyncio.run(self._preload_async(all_phrases))
        print(" ✓")

    async def _preload_async(self, phrases: list[str]):
        lang  = get_lang()
        voice = lang["tts_voice"]
        rate  = lang.get("tts_rate", "+20%")  # чуть быстрее для системных фраз
        tasks = [self._generate_audio(p, voice, rate) for p in phrases]
        paths = await asyncio.gather(*tasks, return_exceptions=True)
        for phrase, path in zip(phrases, paths):
            if isinstance(path, str) and os.path.exists(path):
                self._cache[phrase] = path

    # ── Публичные методы ──────────────────────────────────────────────────────

    def speak(self, text: str):
        """
        Озвучивает текст.
        Если фраза в кэше — воспроизводит мгновенно.
        """
        if not text or not text.strip():
            return
        try:
            lang = get_lang()

            cached = self._cache.get(text)
            if cached and os.path.exists(cached):
                audio_path = cached
                is_cached  = True
            else:
                audio_path = asyncio.run(
                    self._generate_audio(text, lang["tts_voice"], lang["tts_rate"])
                )
                is_cached = False

            if not audio_path:
                return

            TTS.is_speaking = True
            try:
                self._play_audio(audio_path)
            finally:
                time.sleep(0.25)       # ждём затухания эха в комнате
                TTS.is_speaking = False

            if not is_cached:
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

        except Exception as e:
            TTS.is_speaking = False
            print(f"  [!] Ошибка TTS: {e}")

    def speak_activation(self):
        """Случайная фраза активации — говорит сразу из кэша."""
        lang    = get_lang()
        phrases = _ACTIVATION_RU if lang["label"] == "Русский" else _ACTIVATION_EN
        self.speak(random.choice(phrases))

    # ── Внутренние методы ─────────────────────────────────────────────────────

    async def _generate_audio(self, text: str, voice: str, rate: str) -> str | None:
        tmp  = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        path = tmp.name
        tmp.close()
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(path)
        return path

    def _play_audio(self, path: str):
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    def clear_cache(self):
        for path in self._cache.values():
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass
        self._cache.clear()

    def __del__(self):
        self.clear_cache()
        try:
            pygame.mixer.quit()
        except Exception:
            pass