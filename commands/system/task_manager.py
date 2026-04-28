import subprocess
import config

COMMAND_NAME = "task_manager"
DESCRIPTION = (
    "Open Task Manager / Открыть диспетчер задач. "
    "RU triggers: открой диспетчер задач, диспетчер задач, покажи процессы. "
    "EN triggers: open task manager, task manager, show processes."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    subprocess.Popen(["taskmgr.exe"])
    return "Opening Task Manager." if is_en else "Открываю диспетчер задач."