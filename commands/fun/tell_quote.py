import random
import config

COMMAND_NAME = "tell_quote"
DESCRIPTION = (
    "Tell an inspiring or interesting quote / Рассказать вдохновляющую цитату. "
    "RU triggers: расскажи цитату, вдохнови меня, мудрая мысль, цитата дня, "
    "скажи что-нибудь умное, афоризм. "
    "EN triggers: tell me a quote, inspire me, quote of the day, say something wise, "
    "give me a quote."
)
PARAMETERS = {}
REQUIRED = []

_QUOTES_RU = [
    "«Если вы думаете, что можете — вы правы. Если думаете, что не можете — тоже правы.» — Генри Форд",
    "«Простота — это высшая степень утончённости.» — Леонардо да Винчи",
    "«Лучший способ предсказать будущее — создать его.» — Питер Друкер",
    "«Неудача — это просто возможность начать снова, но уже более умно.» — Генри Форд",
    "«Мы можем столкнуться со многими поражениями, но не должны быть побеждены.» — Майя Энджелоу",
    "«Любой достаточно продвинутый технологический прогресс неотличим от магии.» — Артур Кларк",
    "«Инновация отличает лидера от последователя.» — Стив Джобс",
    "«Ваше время ограничено. Не тратьте его, живя чужой жизнью.» — Стив Джобс",
    "«Единственное, что мешает мне учиться — это моё образование.» — Альберт Эйнштейн",
    "«Жить — значит иметь проблемы. Решать проблемы — значит расти.» — Дж. П. Морган",
    "«Люди, достаточно безумные, чтобы думать, что могут изменить мир, и меняют его.» — Стив Джобс",
    "«Прежде чем что-то сделать, нужно что-нибудь быть.» — Иоганн Гёте",
    "«Препятствие на пути становится путём.» — Марк Аврелий",
    "«Тяжело в учении — легко в бою.» — Александр Суворов",
    "«Данные — это новая нефть.» — Клайв Хамби",
]

_QUOTES_EN = [
    "'Whether you think you can or you think you can't — you're right.' — Henry Ford",
    "'Simplicity is the ultimate sophistication.' — Leonardo da Vinci",
    "'The best way to predict the future is to create it.' — Peter Drucker",
    "'Failure is simply the opportunity to begin again, this time more intelligently.' — Henry Ford",
    "'Any sufficiently advanced technology is indistinguishable from magic.' — Arthur C. Clarke",
    "'Innovation distinguishes between a leader and a follower.' — Steve Jobs",
    "'Your time is limited. Don't waste it living someone else's life.' — Steve Jobs",
    "'The only thing that interferes with my learning is my education.' — Albert Einstein",
    "'The people who are crazy enough to think they can change the world are the ones who do.' — Steve Jobs",
    "'The obstacle in the path becomes the path.' — Marcus Aurelius",
    "'Data is the new oil.' — Clive Humby",
    "'It always seems impossible until it's done.' — Nelson Mandela",
    "'In the middle of difficulty lies opportunity.' — Albert Einstein",
    "'First, solve the problem. Then, write the code.' — John Johnson",
    "'Measuring programming progress by lines of code is like measuring aircraft building progress by weight.' — Bill Gates",
]


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    return random.choice(_QUOTES_EN if is_en else _QUOTES_RU)