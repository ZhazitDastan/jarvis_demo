import datetime

COMMAND_NAME = "get_date"
DESCRIPTION = "Сказать текущую дату и день недели"
PARAMETERS = {}
REQUIRED = []

_DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def handler() -> str:
    now = datetime.datetime.now()
    return f"Сегодня {_DAYS[now.weekday()]}, {now.day} {_MONTHS[now.month - 1]} {now.year} года"