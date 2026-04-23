import subprocess

COMMAND_NAME = "lock_pc"
DESCRIPTION = "Заблокировать экран компьютера"
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return "Блокирую экран"