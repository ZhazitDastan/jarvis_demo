import subprocess
import config

COMMAND_NAME = "volume"
DESCRIPTION = (
    "Volume control with percentage / Управление громкостью с процентами. "
    "RU triggers: громкость 30 процентов, установи громкость на 50, "
    "увеличь громкость, уменьши громкость, выключи звук, включи звук, "
    "убавь звук, прибавь звук. "
    "EN triggers: set volume to 50 percent, volume 30, "
    "mute, unmute, volume up, volume down, increase volume, decrease volume. "
    "action: set, up, down, mute, unmute. "
    "percent: 0–100 (only for action=set)."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["set", "up", "down", "mute", "unmute"],
        "description": (
            "set — установить громкость (нужен percent); "
            "up — увеличить на 10%; "
            "down — уменьшить на 10%; "
            "mute — выключить звук; "
            "unmute — включить звук."
        ),
    },
    "percent": {
        "type": "integer",
        "description": "Уровень громкости 0–100. Только при action=set.",
    },
}
REQUIRED = ["action"]

_STEP = 10  # шаг для up/down


def _send_keys(key_code: int, times: int = 1):
    script = f"(New-Object -com WScript.Shell).SendKeys([char]{key_code})"
    for _ in range(times):
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True)


def _set_volume_pycaw(percent: int) -> bool:
    """Устанавливает громкость через pycaw (точно). Возвращает False если не установлен."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, percent / 100.0)), None)
        return True
    except ImportError:
        return False


def _get_volume_pycaw() -> int | None:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return int(volume.GetMasterVolumeLevelScalar() * 100)
    except ImportError:
        return None


def _mute_pycaw(mute: bool) -> bool:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(1 if mute else 0, None)
        return True
    except ImportError:
        return False


def handler(action: str = "up", percent: int = None) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    if action == "mute":
        if not _mute_pycaw(True):
            _send_keys(173)  # VK_VOLUME_MUTE
        return "Sound muted." if is_en else "Звук выключен."

    if action == "unmute":
        if not _mute_pycaw(False):
            _send_keys(173)
        return "Sound on." if is_en else "Звук включён."

    if action == "set":
        if percent is None:
            return (
                "Please specify a volume level (0–100)."
                if is_en else
                "Укажи уровень громкости от 0 до 100."
            )
        percent = max(0, min(100, percent))
        if not _set_volume_pycaw(percent):
            # Fallback — имитируем клавиши (неточно, но работает без pycaw)
            cur = _get_volume_pycaw() or 50
            diff = percent - cur
            if diff > 0:
                _send_keys(175, abs(diff) // 2)   # VK_VOLUME_UP
            elif diff < 0:
                _send_keys(174, abs(diff) // 2)   # VK_VOLUME_DOWN
        return (
            f"Volume set to {percent}%."
            if is_en else
            f"Громкость установлена на {percent}%."
        )

    if action == "up":
        cur = _get_volume_pycaw()
        if cur is not None:
            new = min(100, cur + _STEP)
            _set_volume_pycaw(new)
            return f"Volume: {new}%." if is_en else f"Громкость: {new}%."
        _send_keys(175, _STEP // 2)
        return "Volume increased." if is_en else "Громкость увеличена."

    if action == "down":
        cur = _get_volume_pycaw()
        if cur is not None:
            new = max(0, cur - _STEP)
            _set_volume_pycaw(new)
            return f"Volume: {new}%." if is_en else f"Громкость: {new}%."
        _send_keys(174, _STEP // 2)
        return "Volume decreased." if is_en else "Громкость уменьшена."

    return "Unknown action." if is_en else "Неизвестное действие."