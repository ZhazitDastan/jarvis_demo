import subprocess

COMMAND_NAME = "shutdown_pc"
DESCRIPTION = (
    "Выключить, перезагрузить или усыпить компьютер. "
    "action: shutdown — выключить, restart — перезагрузить, sleep — усыпить"
)
PARAMETERS = {
    "action": {
        "type": "string",
        "description": "Действие: shutdown, restart или sleep",
    }
}
REQUIRED = ["action"]

_ACTIONS = {
    "shutdown": (["shutdown", "/s", "/t", "5"], "Выключаю компьютер через 5 секунд"),
    "restart":  (["shutdown", "/r", "/t", "5"], "Перезагружаю компьютер через 5 секунд"),
    "sleep":    (["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Усыпляю компьютер"),
}


def handler(action: str = "shutdown") -> str:
    action = action.lower().strip()
    if action not in _ACTIONS:
        return f"Неизвестное действие '{action}'. Используй: shutdown, restart или sleep."
    cmd, message = _ACTIONS[action]
    subprocess.Popen(cmd)
    return message