"""
recorder.py — запись аудио с адаптивным шумоподавлением и VAD

Как работает:
  1. КАЛИБРОВКА — 1 секунда в начале: измеряем уровень фонового шума
  2. Порог активации = шум × NOISE_MULTIPLIER (автоматически под комнату)
  3. VAD — ждём голос, пишем, стоп через SILENCE_AFTER сек тишины
  4. Перед сохранением — вычитаем шумовой профиль из аудио (спектральное вычитание)
"""

import os
import wave
import tempfile
import numpy as np
import sounddevice as sd

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
        self.noise_level  = float(np.abs(audio).mean())
        self.noise_profile = audio  # сохраняем профиль для спектрального вычитания
        self.threshold    = self.noise_level * NOISE_MULTIPLIER
        self._calibrated  = True

        print(f"  [✓] Калибровка готова — уровень шума: {self.noise_level:.0f}, "
              f"порог активации: {self.threshold:.0f}          ")

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
                chunk, _ = stream.read(self.chunk_size)
                chunk    = chunk.flatten()
                energy   = float(np.abs(chunk).mean())
                total_chunks += 1

                is_speech = energy > threshold

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

        # Спектральное вычитание шума
        audio_data = self._denoise(audio_data)

        # Нормализация громкости (чтобы Whisper лучше слышал тихую речь)
        audio_data = self._normalize(audio_data)

        # Конвертируем обратно в int16
        audio_int16 = np.clip(audio_data, -32768, 32767).astype(np.int16)

        return self._save_wav(audio_int16)

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
                mag_clean = np.maximum(mag - noise_spectrum * 1.5, mag * 0.1)

                clean_frame = np.fft.irfft(mag_clean * np.exp(1j * phase))
                out[i:i + frame_len] += clean_frame

            return out

        except Exception:
            # Если что-то пошло не так — возвращаем оригинал
            return audio

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Нормализует громкость до 80% от максимума."""
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * 32767 * 0.8
        return audio

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