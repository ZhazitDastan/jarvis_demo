import subprocess
import config

COMMAND_NAME = "brightness"
DESCRIPTION = (
    "Screen brightness control / Управление яркостью экрана. "
    "RU triggers: сделай яркость выше, сделай яркость ниже, установи яркость на 50 процентов, "
    "яркость максимум, яркость минимум. "
    "EN triggers: brightness up, brightness down, set brightness to 50 percent, "
    "increase brightness, decrease brightness. "
    "action: up, down, set. "
    "level: 0-100 (only for action=set)."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "enum": ["up", "down", "set"],
        "description": "up — увеличить; down — уменьшить; set — установить конкретное значение.",
    },
    "level": {
        "type": "integer",
        "description": "Уровень яркости 0–100. Только при action=set.",
    },
}
REQUIRED = ["action"]

_STEP = 20  # шаг для up/down


def _get_brightness() -> int | None:
    """Читает текущую яркость через WMI."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return int(r.stdout.strip())
    except (ValueError, AttributeError):
        return None


def _set_brightness(level: int) -> bool:
    """Устанавливает яркость через WMI. Возвращает True при успехе."""
    level = max(0, min(100, level))
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
         f".WmiSetBrightness(1, {level})"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return r.returncode == 0


def handler(action: str = "up", level: int = None) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"

    not_supported = (
        "Brightness control is not supported on this display."
        if is_en else
        "Управление яркостью не поддерживается на этом дисплее."
    )

    if action == "set":
        if level is None:
            return (
                "Please specify a brightness level (0–100)."
                if is_en else
                "Укажи уровень яркости от 0 до 100."
            )
        ok = _set_brightness(level)
        if not ok:
            return not_supported
        return (
            f"Brightness set to {level}%."
            if is_en else
            f"Яркость установлена на {level}%."
        )

    current = _get_brightness()
    if current is None:
        return not_supported

    if action == "up":
        new_level = min(100, current + _STEP)
    else:
        new_level = max(0, current - _STEP)

    ok = _set_brightness(new_level)
    if not ok:
        return not_supported

    direction = ("increased" if action == "up" else "decreased") if is_en else \
                ("увеличена" if action == "up" else "уменьшена")
    return (
        f"Brightness {direction}: {new_level}%."
        if is_en else
        f"Яркость {direction}: {new_level}%."
    )