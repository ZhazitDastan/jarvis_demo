COMMAND_NAME = "battery_status"
DESCRIPTION = "Узнать уровень заряда батареи ноутбука"
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return "Батарея не обнаружена — возможно, это стационарный компьютер"
        status = "заряжается" if b.power_plugged else "не заряжается"
        return f"Заряд батареи: {int(b.percent)}%, {status}"
    except ImportError:
        return "Для этой команды установи psutil: pip install psutil"