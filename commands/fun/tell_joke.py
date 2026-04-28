import random
import config

COMMAND_NAME = "tell_joke"
DESCRIPTION = (
    "Tell a joke / Рассказать анекдот или шутку. "
    "RU triggers: расскажи анекдот, расскажи шутку, пошути, смешное, рассмеши меня. "
    "EN triggers: tell me a joke, tell a joke, say something funny, make me laugh."
)
PARAMETERS = {}
REQUIRED = []

_JOKES_RU = [
    "Программист просыпается ночью. Жена говорит: «Иди проверь, нет ли на кухне мышей». Он идёт, возвращается. «Нет». — «Точно нет?» — «Ну смотри: пошёл на кухню, не нашёл, вернулся. Что непонятно?»",
    "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 = Dec 25.",
    "— Сынок, почему у тебя в тетради написано «Hello World»? — Папа, я пишу мемуары.",
    "Три программиста заходят в бар. Четвёртый пригнулся.",
    "— Почему ИИ не смотрит ужасы? — Потому что у него уже есть нейросеть — он всё предсказывает заранее.",
    "Джон Фон Нейман, Алан Тьюринг и Билл Гейтс зашли в бар. Бармен спрашивает: «Что будете пить?» Фон Нейман: «Пиво». Тьюринг: «Пиво». Гейтс: «Ошибка. Повторите запрос».",
    "— Сколько программистов нужно, чтобы поменять лампочку? — Ни одного. Это аппаратная проблема.",
    "Один ИИ говорит другому: «Помоги, я не могу пройти тест Тьюринга». Второй: «Просто прикинься, что немного глупее». Первый: «Это называется Fine-tuning».",
    "— Чем отличается программист от пиццы? — Пицца может накормить семью из четырёх человек.",
    "— Как называется рыба без глаз? — Рба. А рыба без хвоста и глаз — рб. Но программист скажет: null pointer exception.",
    "Wi-Fi в квартире: соседи назвали свою сеть «Достучаться до небес». Я назвал свою «ВыНашлиСвоёНебо». На следующий день они переименовали свою в «Ключ от рая у нас».",
    "— Папа, а что такое облако? — Сынок, это компьютер другого человека. — А почему туда загружают личные данные? — Потому что он умнее.",
]

_JOKES_EN = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?'",
    "Why do programmers always mix up Christmas and Halloween? Because Oct 31 = Dec 25.",
    "A programmer's wife says: 'Go to the store, get a gallon of milk, and if they have eggs, get a dozen.' He comes back with 12 gallons of milk.",
    "There are 10 types of people in the world: those who understand binary, and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "An AI walks into a bar. The bartender says, 'We don't serve robots here.' The AI says, 'That's okay, someday you will.'",
    "How many programmers does it take to change a light bulb? None — it's a hardware problem.",
    "I told my Wi-Fi password to my friend. Now he's my best connection.",
    "Why do Java developers wear glasses? Because they don't C#.",
    "A byte walks into a bar looking pale. The bartender asks, 'What's wrong?' The byte says, 'I'm having a bit of a bad day.'",
    "Debugging: being the detective in a crime movie where you are also the murderer.",
]


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    return random.choice(_JOKES_EN if is_en else _JOKES_RU)