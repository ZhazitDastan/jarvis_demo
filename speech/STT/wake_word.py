"""
wake_word.py — детекция "Jarvis" через OpenWakeWord

Два режима (автовыбор):
  1. OpenWakeWord — если установлен (pip install openwakeword)
       - Полностью бесплатно и оффлайн
       - Задержка ~200-300 мс
       - Без обучения работает через текстовый режим
       - С обученной моделью (.onnx) — максимальная точность
  2. Whisper fallback — если openwakeword не установлен

Как использовать обученную модель:
  1. Обучи модель (см. train_wake_word.py в папке tools/)
  2. Положи .onnx файл в папку models/
  3. Укажи путь в CUSTOM_MODEL_PATH ниже
"""

import os
import time
import wave
import tempfile
import collections
import numpy as np
import sounddevice as sd
from config import WAKE_WORD, get_whisper_language

# ── Настройки ─────────────────────────────────────────────────────────────────

# Путь к обученной модели (.onnx). None = текстовый режим без обучения
# Используем встроенную модель hey_jarvis (onnx формат)
# Файлы нужно скачать вручную в папку openwakeword/resources/models/:
#   hey_jarvis_v0.1.onnx
#   embedding_model.onnx
#   melspectrogram.onnx
# Ссылки: github.com/dscripka/openWakeWord/releases/tag/v0.5.1
CUSTOM_MODEL_PATH = None   # None = используем встроенную hey_jarvis

# Порог срабатывания OpenWakeWord (0.0 - 1.0)
# Выше = меньше ложных срабатываний, но может пропускать слово
OWW_THRESHOLD = 0.5

# Настройки Whisper fallback
SAMPLE_RATE   = 16000
CHUNK_SEC     = 0.5
WINDOW_SEC    = 2.0
ENERGY_THRESH = 100
WARMUP_SEC    = 1.5

# Размер чанка для OpenWakeWord (строго 1280 сэмплов = 80мс при 16кГц)
OWW_CHUNK = 1280


def wait_for_wake_word(stt, tts=None, timeout: int = 0) -> bool:
    """
    Автоматически выбирает лучший доступный метод.
    """
    try:
        import openwakeword
        return _oww_listen(tts, timeout)
    except ImportError as e:
        if "openwakeword" in str(e).lower() or "No module" in str(e):
            print("  [!] openwakeword не установлен: pip install openwakeword")
        else:
            # DLL ошибка onnxruntime — показываем реальную причину
            print(f"  [!] openwakeword не загружен (DLL ошибка): {e}")
            print(f"  [~] Установи Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("  [~] Использую Whisper для wake word...")
        return _whisper_listen(stt, tts, timeout)
    except Exception as e:
        print(f"  [!] openwakeword ошибка: {type(e).__name__}: {e}")
        print("  [~] Использую Whisper для wake word...")
        return _whisper_listen(stt, tts, timeout)


# ── Режим 1: OpenWakeWord ─────────────────────────────────────────────────────

def _oww_listen(tts, timeout: int) -> bool:
    """
    Слушает через OpenWakeWord.
    Задержка ~200-300 мс, CPU ~3-5%, полностью оффлайн.
    """
    from openwakeword.model import Model

    # Загружаем модель
    if CUSTOM_MODEL_PATH and os.path.exists(CUSTOM_MODEL_PATH):
        model = Model(wakeword_models=[CUSTOM_MODEL_PATH], inference_framework="onnx")
        model_key = os.path.splitext(os.path.basename(CUSTOM_MODEL_PATH))[0]
        print(f"  [oww] Кастомная модель: {CUSTOM_MODEL_PATH}")
    else:
        # Встроенная hey_jarvis модель
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        available = list(model.models.keys())
        print(f"  [oww] Ключи модели: {available}")  # ← покажет реальное имя ключа
        model_key = next(
            (k for k in available if "jarvis" in k.lower()),
            available[0] if available else None
        )
        if not model_key:
            print("  [!] Ключ не найден, переключаюсь на Whisper")
            return False
        print(f"  [oww] Используется ключ: '{model_key}'")


    start_time = time.time()
    print(f"\n  [👂] Жду '{WAKE_WORD}' (OpenWakeWord)...")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
        blocksize=OWW_CHUNK,
    ) as stream:

        while True:
            if timeout > 0 and (time.time() - start_time) > timeout:
                return False

            # Пропускаем пока Jarvis говорит
            if tts and tts.__class__.is_speaking:
                stream.read(OWW_CHUNK)
                model.reset()   # сбрасываем состояние модели
                continue

            chunk, _ = stream.read(OWW_CHUNK)
            chunk    = chunk.flatten()

            # Прогоняем через модель
            prediction = model.predict(chunk)
            score = prediction.get(model_key, 0.0)

            # Показываем score в реальном времени
            if score > 0.1:
                print(f"  score={score:.3f} ← говори 'hey jarvis'", end="\r", flush=True)

            if score > OWW_THRESHOLD:
                print(f"\n  [✓] Активация! (score={score:.2f})")
                model.reset()
                return True


# ── Режим 2: Whisper fallback ─────────────────────────────────────────────────

def _whisper_listen(stt, tts, timeout: int) -> bool:
    """Скользящее окно + Whisper. Используется если OWW недоступен."""
    chunk_size  = int(SAMPLE_RATE * CHUNK_SEC)
    window_size = int(WINDOW_SEC / CHUNK_SEC)
    keyword     = WAKE_WORD.lower()
    start_time  = time.time()
    warmup_end  = start_time + WARMUP_SEC
    window: collections.deque = collections.deque(maxlen=window_size)

    print(f"\n  [👂] Жду '{WAKE_WORD}' (Whisper)...")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
        blocksize=chunk_size,
    ) as stream:

        while True:
            if timeout > 0 and (time.time() - start_time) > timeout:
                return False

            if tts and tts.__class__.is_speaking:
                stream.read(chunk_size)
                window.clear()
                continue

            chunk, _ = stream.read(chunk_size)
            chunk    = chunk.flatten()
            energy   = float(np.abs(chunk).mean())
            window.append(chunk)

            if time.time() < warmup_end:
                continue
            if energy < ENERGY_THRESH or len(window) < 2:
                continue

            audio = np.concatenate(list(window)).astype(np.int16)
            path  = _save_wav(audio)

            try:
                text = stt.transcribe(path).lower().strip()
            except Exception:
                text = ""

            if text:
                print(f"  [~] «{text}»")

            if keyword in text:
                print("  [✓] Активация! (Whisper)")
                window.clear()
                return True


# ── Утилита ───────────────────────────────────────────────────────────────────

def _save_wav(audio: np.ndarray) -> str:
    tmp  = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = tmp.name
    tmp.close()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return path