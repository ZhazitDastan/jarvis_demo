"""
api/server.py — FastAPI backend для фронта (React + Vite + Tauri)

Запуск: uvicorn api.server:app --reload --port 8000
"""

import sys
import os
import time
import datetime
import logging
import threading
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# DLL-пути на Windows (как в main.py)
if hasattr(os, "add_dll_directory") and sys.platform == "win32":
    import site
    for _sp in site.getsitepackages():
        for _pkg in ("torch/lib", "onnxruntime/capi"):
            _dll_dir = os.path.join(_sp, _pkg.replace("/", os.sep))
            if os.path.isdir(_dll_dir):
                os.add_dll_directory(_dll_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil

# ── Логгер ────────────────────────────────────────────────────────────────────

LOG_FILE = Path("logs/assistant.log")
LOG_FILE.parent.mkdir(exist_ok=True)

_logger = logging.getLogger("jarvis")
_logger.setLevel(logging.DEBUG)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
_logger.addHandler(_file_handler)

# ── Переводы лог-сообщений ────────────────────────────────────────────────────

_LOG = {
    "ru": {
        "preload_start":    "Предзагрузка моделей...",
        "tts_ok":           "TTS загружен",
        "tts_fail":         "TTS не загружен: %s",
        "brain_ok":         "Brain загружен",
        "brain_fail":       "Brain не загружен: %s",
        "stt_ok":           "STT загружен",
        "stt_fail":         "STT не загружен: %s",
        "indexer_ok":       "Файловый индексатор запущен",
        "indexer_fail":     "Файловый индексатор не загружен: %s",
        "preload_done":     "Предзагрузка завершена",
        "voice_user":       "Голос | Пользователь: %s",
        "voice_jarvis":     "Голос | Jarvis: %s",
        "chat_user":        "Чат  | Пользователь: %s",
        "chat_jarvis":      "Чат  | Jarvis: %s",
        "started":          "Jarvis запущен (язык: %s)",
        "stopped":          "Jarvis остановлен",
        "audio_restart":    "Аудио-стрим прерван, перезапуск через 2с: %s",
        "recorder_reinit":  "Переинициализация рекордера: %s",
        "voice_error":      "Ошибка голосового цикла: %s",
        "mic_changed":      "Микрофон сменён: [%d] %s",
        "mic_restarted":    "Голосовой цикл перезапущен с новым микрофоном",
    },
    "en": {
        "preload_start":    "Preloading models...",
        "tts_ok":           "TTS loaded",
        "tts_fail":         "TTS failed to load: %s",
        "brain_ok":         "Brain loaded",
        "brain_fail":       "Brain failed to load: %s",
        "stt_ok":           "STT loaded",
        "stt_fail":         "STT failed to load: %s",
        "indexer_ok":       "File indexer started",
        "indexer_fail":     "File indexer failed to load: %s",
        "preload_done":     "Preloading complete",
        "voice_user":       "Voice | User: %s",
        "voice_jarvis":     "Voice | Jarvis: %s",
        "chat_user":        "Chat  | User: %s",
        "chat_jarvis":      "Chat  | Jarvis: %s",
        "started":          "Jarvis started (language: %s)",
        "stopped":          "Jarvis stopped",
        "audio_restart":    "Audio stream interrupted, restarting in 2s: %s",
        "recorder_reinit":  "Recorder reinitialization: %s",
        "voice_error":      "Voice loop error: %s",
        "mic_changed":      "Microphone changed: [%d] %s",
        "mic_restarted":    "Voice loop restarted with new microphone",
    },
}


def _lm(key: str, *args) -> str:
    """Возвращает лог-сообщение на активном языке."""
    lang = getattr(config, "ACTIVE_LANGUAGE", "ru")
    msg  = _LOG.get(lang, _LOG["ru"]).get(key, key)
    return msg % args if args else msg


import config
import ai.brain as _brain_module
from config import set_language, LANGUAGE_PROFILES, get_lang
from ai.brain import Brain
from commands import COMMANDS, execute_command
from speech.TTS.tts_v3 import TTS
import services.events as _events
from api.files import router as _files_router

# ── App ───────────────────────────────────────────────────────────────────────

def _preload_models():
    """Загружает все модели при старте сервера в фоновом потоке."""
    _logger.info(_lm("preload_start"))
    try:
        get_tts()
        _logger.info(_lm("tts_ok"))
    except Exception as e:
        _logger.warning(_lm("tts_fail", e))
    try:
        if config.OPENAI_API_KEY:
            get_brain()
            _logger.info(_lm("brain_ok"))
    except Exception as e:
        _logger.warning(_lm("brain_fail", e))
    try:
        import speech.STT.stt as _stt_mod
        from speech.STT.stt import get_stt
        from utils.ramdisk import setup_vosk_ramdisk
        _stt_mod.VOSK_MODEL_PATH = setup_vosk_ramdisk(_stt_mod.VOSK_MODEL_PATH)
        get_stt()
        _logger.info(_lm("stt_ok"))
    except Exception as e:
        _logger.warning(_lm("stt_fail", e))
    try:
        from database.files.file_indexer import get_indexer
        get_indexer()
        _logger.info(_lm("indexer_ok"))
    except Exception as e:
        _logger.warning(_lm("indexer_fail", e))
    _logger.info(_lm("preload_done"))


@asynccontextmanager
async def lifespan(application: FastAPI):
    _State.set_loop(asyncio.get_running_loop())
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _preload_models)   # фон, не блокирует старт
    yield


app = FastAPI(title="Jarvis API", version="1.0.0", lifespan=lifespan)
app.include_router(_files_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tauri: tauri://localhost или http://localhost:1420
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Общее состояние ───────────────────────────────────────────────────────────

class _State:
    status: str = "idle"          # idle | listening | thinking | speaking
    is_running: bool = False
    voice_busy: bool = False      # True пока голосовой цикл обрабатывает команду
    active_mic_index: Optional[int] = None
    followup_seconds: int = 12
    _clients: list[WebSocket] = []
    _loop: Optional[asyncio.AbstractEventLoop] = None
    chat_history: list = []
    _MAX_HISTORY: int = 200

    @classmethod
    def set_loop(cls, loop: asyncio.AbstractEventLoop):
        cls._loop = loop

    @classmethod
    async def _broadcast(cls, event: dict):
        dead = []
        for ws in cls._clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            cls._clients.remove(ws)

    @classmethod
    def emit(cls, event: dict):
        """Отправить событие всем WS-клиентам из любого потока."""
        if cls._loop and not cls._loop.is_closed():
            asyncio.run_coroutine_threadsafe(cls._broadcast(event), cls._loop)

    @classmethod
    def set_status(cls, status: str):
        cls.status = status
        cls.emit({"type": "status", "value": status})

    @classmethod
    def add_message(cls, role: str, text: str):
        cls.chat_history.append({
            "role": role,
            "text": text,
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
        })
        if len(cls.chat_history) > cls._MAX_HISTORY:
            cls.chat_history = cls.chat_history[-cls._MAX_HISTORY:]


# ── Синглтоны Brain и TTS ─────────────────────────────────────────────────────

_brain: Optional[Brain] = None
_tts: Optional[TTS] = None
_brain_lock = threading.Lock()


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain


def get_tts() -> TTS:
    global _tts
    if _tts is None:
        _tts = TTS()
    return _tts


# ── Голосовой цикл ────────────────────────────────────────────────────────────

class VoiceRunner:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop  = threading.Event()
        self._lock  = threading.Lock()

    def start(self):
        with self._lock:
            if _State.is_running:
                return
            _State.is_running = True   # устанавливаем до старта потока
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        _State.is_running = False
        _State.set_status("idle")

    def _run(self):
        try:
            import speech.STT.stt as _stt_mod
            from speech.STT.stt import get_stt
            from speech.STT.recorder import Recorder
            from speech.STT.wake_word import wait_for_wake_word, StopListener
            from utils.ramdisk import setup_vosk_ramdisk

            _stt_mod.VOSK_MODEL_PATH = setup_vosk_ramdisk(_stt_mod.VOSK_MODEL_PATH)

            stt      = get_stt()
            recorder = Recorder()
            recorder.calibrate()
            tts      = get_tts()
            brain    = get_brain()

            tts.speak(get_lang()["ready"])

            while not self._stop.is_set():
                try:
                    _State.set_status("idle")

                    # Шаг 1: Ждём wake word
                    wait_for_wake_word(stt=stt, tts=tts, stop_event=self._stop)
                    if self._stop.is_set():
                        break

                    lang = get_lang()
                    _State.emit({"type": "wake_word"})
                    tts.speak(lang["activation"])

                    # Шаг 2: Запись команды
                    _State.set_status("listening")
                    audio_path = recorder.record(max_seconds=config.LISTEN_TIMEOUT)
                    if not audio_path or self._stop.is_set():
                        continue

                    _State.set_status("thinking")
                    text = stt.transcribe(audio_path)
                    if not text or len(text.strip()) < 2:
                        _State.set_status("idle")
                        continue

                    _State.emit({"type": "transcribed", "text": text})
                    _State.add_message("user", text)
                    _logger.info(_lm("voice_user", text))

                    stop_words = lang.get("stop_words", [])
                    if any(w in text.lower() for w in stop_words):
                        tts.speak(lang.get("stopped", "Хорошо."))
                        _State.set_status("idle")
                        continue

                    # Шаг 3: GPT → TTS
                    _State.voice_busy = True
                    try:
                        with _brain_lock:
                            response = brain.think(text)
                    finally:
                        _State.voice_busy = False

                    _logger.info(_lm("voice_jarvis", response))
                    _State.add_message("assistant", response)
                    _State.emit({"type": "response", "text": response})
                    _State.set_status("speaking")
                    with StopListener(stt, tts):
                        tts.speak(response)

                    # Шаг 4: Followup
                    # Пауза 0.6с — даём эху TTS затухнуть, иначе микрофон
                    # подхватывает конец ответа Jarvis как новую команду
                    time.sleep(0.6)
                    followup_end = time.time() + _State.followup_seconds
                    while time.time() < followup_end and not self._stop.is_set():
                        _State.set_status("listening")
                        audio_path = recorder.record(max_seconds=config.LISTEN_TIMEOUT)
                        if not audio_path:
                            break

                        text = stt.transcribe(audio_path)
                        if not text or len(text.strip()) < 2:
                            break

                        _State.emit({"type": "transcribed", "text": text})
                        _State.add_message("user", text)

                        if any(w in text.lower() for w in stop_words):
                            tts.stop()
                            break

                        if "jarvis" in text.lower():
                            text = text.lower().replace("jarvis", "").strip()
                            if not text:
                                tts.speak(lang["listening"])
                                continue

                        _State.set_status("thinking")
                        _State.voice_busy = True
                        try:
                            with _brain_lock:
                                response = brain.think(text)
                        finally:
                            _State.voice_busy = False

                        _State.add_message("assistant", response)
                        _State.emit({"type": "response", "text": response})
                        _State.set_status("speaking")
                        with StopListener(stt, tts):
                            tts.speak(response)

                        followup_end = time.time() + _State.followup_seconds

                except Exception as loop_err:
                    s = str(loop_err)
                    if "Stream is stopped" in s or "PaErrorCode" in s:
                        _logger.warning(_lm("audio_restart", loop_err))
                        _State.set_status("idle")
                        _State.voice_busy = False
                        time.sleep(2)
                        try:
                            recorder = Recorder()
                            recorder.calibrate()
                        except Exception as re:
                            _logger.warning(_lm("recorder_reinit", re))
                    else:
                        raise   # не-аудио ошибки поднимаем наверх

        except Exception as e:
            _logger.error(_lm("voice_error", e))
            _State.emit({"type": "error", "message": str(e)})
            _State.is_running = False
            _State.set_status("idle")


_runner = VoiceRunner()
_events.register_emit(_State.emit)

# ── WebSocket /ws ─────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _State._clients.append(ws)
    # Сразу отправляем текущий статус новому клиенту
    await ws.send_json({"type": "status", "value": _State.status, "is_running": _State.is_running})
    try:
        while True:
            await ws.receive_text()   # keep-alive, входящие игнорируем
    except WebSocketDisconnect:
        if ws in _State._clients:
            _State._clients.remove(ws)


# ── GET /status ───────────────────────────────────────────────────────────────

@app.get("/status")
async def get_status():
    return {
        "status":       _State.status,
        "is_running":   _State.is_running,
        "language":     config.ACTIVE_LANGUAGE,
        "wake_word":    config.WAKE_WORD,
        "mic_index":    _State.active_mic_index,
        "openai_ready": bool(config.OPENAI_API_KEY),
    }


# ── POST /jarvis/start · /jarvis/stop ─────────────────────────────────────────

@app.post("/jarvis/start")
async def start_jarvis():
    if not config.OPENAI_API_KEY:
        raise HTTPException(400, "OpenAI API ключ не задан. Укажите в настройках.")
    if _State.is_running:
        return {"ok": True, "message": "Jarvis уже запущен"}
    _runner.start()
    _logger.info(_lm("started", config.ACTIVE_LANGUAGE))
    return {"ok": True, "message": "Jarvis запущен"}


@app.post("/jarvis/stop")
async def stop_jarvis():
    _runner.stop()
    _logger.info(_lm("stopped"))
    return {"ok": True, "message": "Jarvis остановлен"}


# ── POST /chat ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    text: str
    speak: bool = False


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(400, "Пустой запрос")
    if not config.OPENAI_API_KEY:
        raise HTTPException(400, "OpenAI API ключ не задан")
    if _State.voice_busy:
        # Голосовой цикл уже обрабатывает эту команду — дублировать не нужно
        raise HTTPException(409, "Voice pipeline is busy")

    _State.set_status("thinking")
    _State.emit({"type": "transcribed", "text": req.text})

    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: _chat_sync(req.text, req.speak))
        _State.emit({"type": "response", "text": response})
        _State.set_status("idle")
        return {"response": response}
    except Exception as e:
        _State.set_status("idle")
        raise HTTPException(500, str(e))


def _chat_sync(text: str, speak: bool) -> str:
    with _brain_lock:
        response = get_brain().think(text)
    _logger.info(_lm("chat_user", text))
    _logger.info(_lm("chat_jarvis", response))
    _State.add_message("user", text)
    _State.add_message("assistant", response)
    if speak:
        get_tts().speak(response)
    return response


# ── POST /chat/reset ──────────────────────────────────────────────────────────

@app.get("/chat/history")
async def get_chat_history():
    return {"messages": _State.chat_history}


@app.delete("/chat/history/{index}")
async def delete_chat_message(index: int):
    if index < 0 or index >= len(_State.chat_history):
        raise HTTPException(404, f"Сообщение с индексом {index} не найдено")
    _State.chat_history.pop(index)
    return {"ok": True, "remaining": len(_State.chat_history)}


@app.post("/chat/reset")
async def reset_chat():
    with _brain_lock:
        get_brain().reset_history()
    _State.chat_history.clear()
    return {"ok": True}


# ── GET /settings · PATCH /settings ──────────────────────────────────────────

@app.get("/settings")
async def get_settings():
    import speech.TTS.tts_v3 as _tts_mod
    import speech.STT.recorder as _rec_mod
    return {
        "language":          config.ACTIVE_LANGUAGE,
        "languages":         {code: p["label"] for code, p in LANGUAGE_PROFILES.items()},
        "gpt_model":         config.GPT_MODEL,
        "vosk_model":        config.VOSK_MODEL_DIR,
        "listen_timeout":    config.LISTEN_TIMEOUT,
        "wake_word":         config.WAKE_WORD,
        "mic_index":         _State.active_mic_index,
        "openai_key_set":    bool(config.OPENAI_API_KEY),
        "tts_speed":         _tts_mod.LENGTH_SCALE,
        "noise_multiplier":  _rec_mod.NOISE_MULTIPLIER,
        "silence_after":     _rec_mod.SILENCE_AFTER,
        "followup_seconds":  _State.followup_seconds,
        "temperature":       config.GPT_TEMPERATURE,
    }


class SettingsUpdate(BaseModel):
    language:         Optional[str]   = None
    gpt_model:        Optional[str]   = None
    openai_key:       Optional[str]   = None
    vosk_model:       Optional[str]   = None
    listen_timeout:   Optional[int]   = None
    mic_index:        Optional[int]   = None
    tts_speed:        Optional[float] = None
    noise_multiplier: Optional[float] = None
    silence_after:    Optional[float] = None
    followup_seconds: Optional[int]   = None
    temperature:      Optional[float] = None


@app.patch("/settings")
async def update_settings(body: SettingsUpdate):
    global _brain

    if body.language is not None:
        if body.language not in LANGUAGE_PROFILES:
            raise HTTPException(400, f"Неизвестный язык: {body.language}")
        set_language(body.language)
        with _brain_lock:
            get_brain().reset_history()   # сбрасываем историю — старые сообщения на другом языке путают GPT
        _State.chat_history.clear()

    if body.gpt_model is not None:
        config.GPT_MODEL = body.gpt_model
        _brain_module.GPT_MODEL = body.gpt_model   # патчим импортированную переменную

    if body.openai_key is not None:
        config.OPENAI_API_KEY = body.openai_key
        os.environ["OPENAI_API_KEY"] = body.openai_key
        _brain_module.OPENAI_API_KEY = body.openai_key
        _brain = None                               # пересоздаём Brain с новым ключом

    if body.vosk_model is not None:
        config.VOSK_MODEL_DIR = body.vosk_model

    if body.listen_timeout is not None:
        config.LISTEN_TIMEOUT = body.listen_timeout

    if body.mic_index is not None:
        _State.active_mic_index = body.mic_index

    if body.tts_speed is not None:
        import speech.TTS.tts_v3 as _tts_mod
        _tts_mod.LENGTH_SCALE = body.tts_speed

    if body.noise_multiplier is not None:
        import speech.STT.recorder as _rec_mod
        _rec_mod.NOISE_MULTIPLIER = body.noise_multiplier

    if body.silence_after is not None:
        import speech.STT.recorder as _rec_mod
        _rec_mod.SILENCE_AFTER = body.silence_after

    if body.followup_seconds is not None:
        _State.followup_seconds = body.followup_seconds

    if body.temperature is not None:
        config.GPT_TEMPERATURE = body.temperature
        _brain_module.GPT_TEMPERATURE = body.temperature

    return {"ok": True}


# ── GET /microphones ──────────────────────────────────────────────────────────

_MIC_BLOCKLIST = [
    # Windows виртуальные маперы
    "sound mapper", "primary sound", "первичный драйвер",
    # Микшеры и петли
    "stereo mix", "стерео микшер",
    # Steam виртуальные устройства
    "steam streaming",
    # Линейные входы без устройства
    "линия ()", "line ()",
    # Динамики / выходы
    "динамик", "speaker", "output",
]

_MIN_SAMPLE_RATE = 16000   # ниже этого STT работает плохо

def _is_real_mic(name: str, sample_rate: int) -> bool:
    low = name.lower()
    if any(blocked in low for blocked in _MIC_BLOCKLIST):
        return False
    # Bluetooth HFP (bthhfenum) пропускаем если >= 16kHz, иначе скрываем
    if "bthhfenum" in low and sample_rate < _MIN_SAMPLE_RATE:
        return False
    return True


@app.get("/microphones")
async def list_microphones():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_idx = _get_default_mic_idx(devices)

        mics = []
        for i, d in enumerate(devices):
            sr = int(d["default_samplerate"])
            if d["max_input_channels"] > 0 and _is_real_mic(d["name"], sr):
                mics.append({
                    "index":       i,
                    "name":        d["name"],
                    "channels":    d["max_input_channels"],
                    "sample_rate": int(d["default_samplerate"]),
                    "is_default":  i == default_idx,
                })
        return {"microphones": mics, "active_index": _State.active_mic_index}
    except Exception as e:
        raise HTTPException(500, f"Не удалось получить микрофоны: {e}")


# ── GET /neural ───────────────────────────────────────────────────────────────

@app.get("/neural")
async def get_neural():
    import speech.STT.stt as _stt_mod

    lang = config.ACTIVE_LANGUAGE

    # STT: Vosk RU или Vosk EN (Faster-Whisper удалён)
    stt_instance = _stt_mod._instance
    if lang == "ru":
        model_name = os.path.basename(config.VOSK_MODEL_DIR)
        stt_loaded = stt_instance is not None and stt_instance._vosk_model is not None
        stt_info   = {"engine": "Vosk RU", "model": model_name, "loaded": stt_loaded}
    else:
        model_name = os.path.basename(config.VOSK_EN_MODEL_DIR)
        stt_loaded = stt_instance is not None and stt_instance._vosk_model_en is not None
        stt_info   = {"engine": "Vosk EN", "model": model_name, "loaded": stt_loaded}

    # TTS: Edge TTS (Microsoft Azure Neural, бесплатно)
    tts_instance = _tts
    voice_names  = {"ru": "ru-RU-DmitryNeural", "en": "en-GB-RyanNeural"}
    tts_loaded   = tts_instance is not None
    tts_info     = {"engine": "Edge TTS", "model": voice_names.get(lang, "—"), "loaded": tts_loaded}

    return {"stt": stt_info, "tts": tts_info}


# ── GET /commands ─────────────────────────────────────────────────────────────

@app.get("/commands")
async def list_commands():
    return {
        "commands": [
            {
                "name":        name,
                "description": meta.get("description", ""),
                "params":      meta.get("params", {}),
            }
            for name, meta in COMMANDS.items()
        ]
    }


# ── GET /microphone/active ────────────────────────────────────────────────────

def _get_default_mic_idx(devices) -> int:
    """Находит индекс дефолтного микрофона через query_devices(kind='input')."""
    try:
        import sounddevice as sd
        default_name = sd.query_devices(kind="input")["name"]
        for i, d in enumerate(devices):
            if d["name"] == default_name and d["max_input_channels"] > 0:
                return i
    except Exception:
        pass
    # Fallback: первый доступный микрофон
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            return i
    return 0


@app.get("/microphone/active")
async def get_active_microphone():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_idx = _get_default_mic_idx(devices)
        idx = _State.active_mic_index if _State.active_mic_index is not None else default_idx

        if idx >= len(devices):
            return {"index": None, "name": "Микрофон не найден"}

        d = devices[idx]
        return {
            "index":       idx,
            "name":        d["name"],
            "channels":    d["max_input_channels"],
            "sample_rate": int(d["default_samplerate"]),
            "is_default":  idx == default_idx,
        }
    except Exception as e:
        raise HTTPException(500, f"Не удалось получить микрофон: {e}")


class MicUpdate(BaseModel):
    index:     Optional[int] = None
    mic_index: Optional[int] = None   # алиас для совместимости с /settings

    def resolved(self) -> int:
        v = self.index if self.index is not None else self.mic_index
        if v is None:
            raise ValueError("Укажите index или mic_index")
        return v


@app.patch("/microphone/active")
async def set_active_microphone(body: MicUpdate):
    try:
        idx = body.resolved()
        import sounddevice as sd
        devices = sd.query_devices()

        if idx >= len(devices) or devices[idx]["max_input_channels"] == 0:
            raise HTTPException(400, f"Микрофон с индексом {idx} не найден")

        was_running = _State.is_running

        if was_running:
            _runner.stop()

        _State.active_mic_index = idx
        mic_name = devices[idx]["name"]
        _logger.info(_lm("mic_changed", idx, mic_name))

        if was_running:
            _runner.start()
            _logger.info(_lm("mic_restarted"))

        return {
            "ok":          True,
            "index":       idx,
            "name":        mic_name,
            "restarted":   was_running,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Не удалось сменить микрофон: {e}")


# ── GET /resources ────────────────────────────────────────────────────────────

def _collect_resources() -> dict:
    """Блокирующий сбор метрик — запускается в executor."""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    result: dict = {
        "cpu":    round(cpu, 1),
        "memory": round(mem.percent, 1),
        "disk":   round(disk.percent, 1),
    }
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            result["gpu_name"]    = g.name
            result["gpu_load"]    = round(g.load * 100, 1)
            result["gpu_memory"]  = round(g.memoryUtil * 100, 1)
    except Exception:
        pass
    return result


@app.get("/resources")
async def get_resources():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _collect_resources)


# ── GET /logs · DELETE /logs ──────────────────────────────────────────────────

@app.get("/logs")
async def get_logs(lines: int = 200):
    if not LOG_FILE.exists():
        return {"logs": ""}
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        tail = text.splitlines()[-lines:]
        return {"logs": "\n".join(tail)}
    except Exception as e:
        raise HTTPException(500, f"Ошибка чтения логов: {e}")


@app.delete("/logs")
async def clear_logs():
    if LOG_FILE.exists():
        LOG_FILE.write_text("", encoding="utf-8")
    return {"ok": True}

