"""
recorder.py — запись аудио с адаптивным шумоподавлением и VAD

Как работает:
  1. КАЛИБРОВКА — 1 секунда в начале: измеряем уровень фонового шума
  2. Порог активации = шум × NOISE_MULTIPLIER (автоматически под комнату)
  3. VAD — ждём голос, пишем, стоп через SILENCE_AFTER сек тишины
      Приоритет: webrtcvad (если установлен) → energy-based (fallback)
  4. Перед сохранением — вычитаем шумовой профиль из аудио (спектральное вычитание)
"""

import os
import wave
import tempfile
import numpy as np
import sounddevice as sd

try:
    import webrtcvad as _webrtcvad
    _VAD_AVAILABLE = True
except ImportError:
    _webrtcvad    = None
    _VAD_AVAILABLE = False

# ── Настройки ──────────────────────────────────────────────────────────────────
NOISE_MULTIPLIER  = 3.5   # порог = шум × это число (выше → игнорирует больше шума)
SILENCE_AFTER     = 2.0   # секунд тишины после речи → стоп
START_TIMEOUT     = 6.0   # секунд ждать начала речи до сдачи
CALIBRATION_SEC   = 1.0   # секунд на замер фонового шума
SAMPLE_RATE       = 16000
CHUNK_MS          = 100   # мс на один чанк


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate  = sample_rate
        self.channels     = 1
        self.chunk_size   = int(sample_rate * CHUNK_MS / 1000)
        self.noise_level  = 300   # дефолт, перезапишется при калибровке
        self.threshold    = 300 * NOISE_MULTIPLIER
        self._calibrated  = False
        self._vad         = None
        if _VAD_AVAILABLE:
            try:
                # 1 = мягкий (0 — отключён, 3 — максимально агрессивный)
                # 1 лучше для акцентированной речи и тихих голосов
                self._vad = _webrtcvad.Vad(1)
            except Exception:
                pass

    # ── Калибровка шума ────────────────────────────────────────────────────────

    def calibrate(self):
        """
        Слушает CALIBRATION_SEC секунд тишины и вычисляет уровень фонового шума.
        Вызывается один раз при старте из main.py.
        """
        print("  [~] Калибровка микрофона... (не говорите)", end="\r", flush=True)

        n_samples = int(self.sample_rate * CALIBRATION_SEC)
        audio = sd.rec(n_samples, samplerate=self.sample_rate,
                       channels=1, dtype=np.int16)
        sd.wait()

        audio = audio.flatten().astype(np.float32)
        self.noise_level  = float(np.sqrt(np.mean(audio ** 2)))  # RMS шума
        self.noise_profile = audio  # сохраняем профиль для спектрального вычитания
        self.threshold    = self.noise_level * NOISE_MULTIPLIER
        self._calibrated  = True

        vad_engine = "webrtcvad" if self._vad else "energy-based"
        print(f"  [✓] Калибровка готова — уровень шума: {self.noise_level:.0f}, "
              f"порог: {self.threshold:.0f}  [{vad_engine}]          ")

    # ── Подготовка ────────────────────────────────────────────────────────────

    def prepare(self):
        """
        Предварительно инициализирует аудио систему — готовит stream к записи.
        Вызывается после активационной фразы чтобы избежать задержки.
        """
        if not self._calibrated:
            return
        try:
            # Открываем и закрываем dummy stream чтобы инициализировать аудиосистему
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.int16,
                blocksize=self.chunk_size,
            ) as stream:
                stream.read(self.chunk_size)
        except Exception:
            pass   # не критично если prepare() не удалась

    # ── Запись с VAD ───────────────────────────────────────────────────────────

    def record(self, max_seconds: int = 15) -> str | None:
        """
        Записывает речь с VAD и шумоподавлением.
        Возвращает путь к WAV файлу или None.
        """
        if not self._calibrated:
            self.calibrate()

        threshold       = self.threshold
        frames_all:     list[np.ndarray] = []
        silence_chunks  = 0
        speech_started  = False
        speech_frames   = 0
        total_chunks    = 0
        max_chunks      = int(max_seconds * 1000 / CHUNK_MS)
        start_timeout_c = int(START_TIMEOUT * 1000 / CHUNK_MS)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.int16,
            blocksize=self.chunk_size,
        ) as stream:

            while total_chunks < max_chunks:
                try:
                    chunk, _ = stream.read(self.chunk_size)
                except Exception as e:
                    if "Stream is stopped" in str(e) or "PaErrorCode" in str(e):
                        return None   # аудиоустройство отключилось, выходим чисто
                    raise
                chunk    = chunk.flatten()
                energy   = float(np.abs(chunk).mean())
                total_chunks += 1

                is_speech = self._is_speech_vad(chunk, energy)

                if not speech_started:
                    if is_speech:
                        speech_started = True
                        frames_all.append(chunk)
                        speech_frames += 1
                        print("  [●] Говорите...              ", end="\r", flush=True)
                    elif total_chunks > start_timeout_c:
                        print("  [!] Речь не обнаружена.      ")
                        return None
                else:
                    frames_all.append(chunk)

                    if not is_speech:
                        silence_chunks += 1
                        secs = silence_chunks * CHUNK_MS / 1000
                        bar  = "█" * int(secs / SILENCE_AFTER * 10)
                        print(f"  [■] Тишина {secs:.1f}с [{bar:<10}]",
                              end="\r", flush=True)

                        if silence_chunks >= int(SILENCE_AFTER * 1000 / CHUNK_MS):
                            print()
                            break
                    else:
                        silence_chunks = 0
                        speech_frames += 1

        print()

        if not frames_all or speech_frames < 3:
            return None

        # Собираем аудио
        audio_data = np.concatenate(frames_all, axis=0).astype(np.float32)

        # Отклоняем аудио, едва громче фона — иначе _normalize() усиливает шум
        # и Whisper галлюцинирует. Порог 1.3×RMS_шума: речь обычно 3–10× громче.
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        if rms < self.noise_level * 1.3:
            print(f"  [!] Аудио слишком тихое — пропуск (rms={rms:.0f} < порог={self.noise_level * 1.3:.0f}).")
            return None

        # Денойз нужен только в шумной комнате. Для чистого сигнала FFT
        # просто жжёт CPU (~50-100мс на 5 сек аудио) и ничего не улучшает.
        # SNR > 4× — речь и так в 4 раза громче фона, шум не критичен.
        if rms < self.noise_level * 4.0:
            audio_data = self._denoise(audio_data)

        # Нормализация громкости (только если сигнал значительно выше шума)
        audio_data = self._normalize(audio_data)

        # Конвертируем обратно в int16
        audio_int16 = np.clip(audio_data, -32768, 32767).astype(np.int16)

        return self._save_wav(audio_int16)

    # ── VAD ───────────────────────────────────────────────────────────────────

    def _is_speech_vad(self, chunk: np.ndarray, energy: float) -> bool:
        """
        Определяет наличие речи в чанке.
        webrtcvad: делит чанк на 30-мс фреймы, голосует большинством.
        Fallback на energy-threshold если webrtcvad не установлен.
        """
        # Быстрый фильтр: явная тишина — не гоняем через VAD
        if energy < self.threshold * 0.25:
            return False

        if self._vad is None:
            return energy > self.threshold

        frame_samples = int(self.sample_rate * 0.030)  # 480 @ 16kHz
        audio_int16   = chunk.astype(np.int16)
        n_speech = n_total = 0

        for i in range(0, len(audio_int16) - frame_samples + 1, frame_samples):
            frame = audio_int16[i:i + frame_samples].tobytes()
            n_total += 1
            try:
                if self._vad.is_speech(frame, self.sample_rate):
                    n_speech += 1
            except Exception:
                pass

        if n_total == 0:
            return energy > self.threshold
        return (n_speech / n_total) >= 0.3

    # ── Обработка аудио ────────────────────────────────────────────────────────

    def _denoise(self, audio: np.ndarray) -> np.ndarray:
        """
        Спектральное вычитание: убирает постоянный фоновый шум.
        Работает через FFT — вычитает усреднённый спектр шума из сигнала.
        """
        try:
            frame_len = 512
            hop       = frame_len // 2

            # Строим шумовой профиль из калибровки
            noise_ref = self.noise_profile.astype(np.float32)
            noise_spectrum = np.zeros(frame_len // 2 + 1)
            n_noise_frames = 0
            for i in range(0, len(noise_ref) - frame_len, hop):
                frame = noise_ref[i:i + frame_len] * np.hanning(frame_len)
                noise_spectrum += np.abs(np.fft.rfft(frame))
                n_noise_frames += 1
            if n_noise_frames > 0:
                noise_spectrum /= n_noise_frames

            # Вычитаем шум из каждого фрейма сигнала
            out = np.zeros_like(audio)
            for i in range(0, len(audio) - frame_len, hop):
                frame   = audio[i:i + frame_len] * np.hanning(frame_len)
                spectrum = np.fft.rfft(frame)
                mag      = np.abs(spectrum)
                phase    = np.angle(spectrum)

                # Вычитаем шумовой профиль (с ограничением снизу чтобы не уходить в минус)
                mag_clean = np.maximum(mag - noise_spectrum * 1.0, mag * 0.1)

                clean_frame = np.fft.irfft(mag_clean * np.exp(1j * phase))
                out[i:i + frame_len] += clean_frame

            return out

        except Exception:
            # Если что-то пошло не так — возвращаем оригинал
            return audio

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Нормализует громкость до 80% от максимума.
        Не усиливает сигналы близкие к уровню фонового шума."""
        peak = np.abs(audio).max()
        # Если пик ниже 1.5× RMS шума — сигнал слишком близок к фону
        if peak < self.noise_level * 1.5 or peak == 0:
            return audio
        return audio / peak * 32767 * 0.8

    def _save_wav(self, audio: np.ndarray) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = tmp.name
        tmp.close()

        with wave.open(path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

        return path

    def cleanup(self, file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass