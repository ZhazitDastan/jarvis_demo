import config

COMMAND_NAME = "system_info"
DESCRIPTION = (
    "Show CPU, RAM, disk usage / Показать загрузку ЦП, ОЗУ, диска. "
    "RU triggers: загрузка процессора, сколько памяти, состояние системы, "
    "покажи статистику, как работает компьютер, нагрузка на систему. "
    "EN triggers: cpu usage, ram usage, system stats, how is the computer doing, system info."
)
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    try:
        import psutil

        cpu  = psutil.cpu_percent(interval=0.5)
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        mem_used = mem.used  // (1024 ** 3)
        mem_total = mem.total // (1024 ** 3)

        if is_en:
            return (
                f"CPU: {cpu}%. "
                f"RAM: {mem_used} of {mem_total} GB used ({mem.percent}%). "
                f"Disk C: {disk.percent}% used."
            )
        return (
            f"Процессор: {cpu}%. "
            f"ОЗУ: {mem_used} из {mem_total} ГБ занято ({mem.percent}%). "
            f"Диск C: {disk.percent}% занято."
        )
    except ImportError:
        return (
            "Install psutil for system info: pip install psutil"
            if is_en else
            "Для системной информации установи psutil: pip install psutil"
        )