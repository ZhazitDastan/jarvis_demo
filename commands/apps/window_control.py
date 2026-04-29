import config

COMMAND_NAME = "window_control"
DESCRIPTION = (
    "Control the active window or switch between applications. "
    "/ Управление активным окном и переключение между приложениями. "

    "Actions: "
    "switch — переключить/switch app (Alt+Tab); "
    "maximize — развернуть/maximize window (Win+Up); "
    "minimize — свернуть/minimize window (Win+Down); "
    "close — закрыть/close window (Alt+F4); "
    "restore — восстановить/restore all minimized (Win+Shift+M); "
    "task_view — все окна/all windows view (Win+Tab); "
    "snap_left — прикрепить влево/snap left (Win+Left); "
    "snap_right — прикрепить вправо/snap right (Win+Right). "

    "RU triggers: "
    "переключи приложение, смени окно, свени приложения, переключись, следующее окно → switch; "
    "разверни окно, на весь экран, увеличь окно, максимизируй → maximize; "
    "сверни окно, минимизируй → minimize; "
    "закрой окно, закрой это → close; "
    "восстанови окна → restore; "
    "покажи все окна, таск вью → task_view; "
    "прикрепи влево → snap_left; прикрепи вправо → snap_right. "

    "EN triggers: "
    "switch app, switch window, next app, toggle window → switch; "
    "maximize window, full screen, make bigger → maximize; "
    "minimize window, hide window → minimize; "
    "close window, close this → close; "
    "restore windows → restore; "
    "show all windows, task view → task_view; "
    "snap left → snap_left; snap right → snap_right."
)
PARAMETERS = {
    "action": {
        "type": "string",
        "description": "switch / maximize / minimize / close / restore / task_view / snap_left / snap_right",
        "enum": ["switch", "maximize", "minimize", "close", "restore", "task_view", "snap_left", "snap_right"],
    }
}
REQUIRED = ["action"]

_KEYS = {
    "switch":     ("alt", "tab"),
    "maximize":   ("win", "up"),
    "minimize":   ("win", "down"),
    "close":      ("alt", "f4"),
    "restore":    ("win", "shift", "m"),
    "task_view":  ("win", "tab"),
    "snap_left":  ("win", "left"),
    "snap_right": ("win", "right"),
}

_LABELS_RU = {
    "switch":     "Переключаю приложение",
    "maximize":   "Разворачиваю окно",
    "minimize":   "Сворачиваю окно",
    "close":      "Закрываю окно",
    "restore":    "Восстанавливаю окна",
    "task_view":  "Показываю все окна",
    "snap_left":  "Прикрепляю окно влево",
    "snap_right": "Прикрепляю окно вправо",
}
_LABELS_EN = {
    "switch":     "Switching application",
    "maximize":   "Maximizing window",
    "minimize":   "Minimizing window",
    "close":      "Closing window",
    "restore":    "Restoring windows",
    "task_view":  "Showing all windows",
    "snap_left":  "Snapping window left",
    "snap_right": "Snapping window right",
}


def handler(action: str) -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    action = action.lower().strip()

    keys = _KEYS.get(action)
    if not keys:
        return (f"Unknown action: {action}" if is_en
                else f"Неизвестное действие: {action}")

    try:
        import pyautogui
        import time
        pyautogui.hotkey(*keys)
        time.sleep(0.1)
        labels = _LABELS_EN if is_en else _LABELS_RU
        return labels.get(action, action)
    except ImportError:
        return "Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"Error: {e}" if is_en else f"Ошибка: {e}"