import random
import config

COMMAND_NAME = "tell_fact"
DESCRIPTION = (
    "Tell an interesting fact / Рассказать интересный факт. "
    "RU triggers: расскажи факт, интересный факт, удиви меня, что-нибудь интересное, "
    "расскажи что-то новое. "
    "EN triggers: tell me a fact, interesting fact, surprise me, something interesting, "
    "share a fact."
)
PARAMETERS = {}
REQUIRED = []

_FACTS_RU = [
    "Осьминоги имеют три сердца, голубую кровь и девять мозгов — один центральный и по одному в каждом щупальце.",
    "Мёд никогда не портится. Археологи находили мёд возрастом более 3000 лет в египетских гробницах — и он был вполне съедобен.",
    "Банан технически является ягодой, а клубника — нет.",
    "Первый компьютерный баг — это буквально насекомое. В 1947 году мотылёк застрял в реле компьютера Гарвардского университета, и Грейс Хоппер вклеила его в журнал с подписью «First actual case of bug being found».",
    "Если сложить все муравьи на Земле, они будут весить столько же, сколько все люди.",
    "Молния бьёт в Землю около 100 раз в секунду — это около 8 миллионов ударов в день.",
    "Кит-горбач знает мелодии. Самцы поют песни длиной до 20 минут, и все особи в океанском регионе поют одну и ту же песню — и постепенно меняют её со временем.",
    "Нейроны в мозге человека передают сигналы со скоростью до 432 км/ч.",
    "Oxford University старше государства Ацтеков: Оксфорд основан в 1096 году, а ацтекская империя — в 1428.",
    "У Cleopatra жила ближе по времени к высадке на Луне, чем к строительству пирамид.",
    "Буква Ё появилась в русском алфавите позже всех остальных — в 1783 году.",
    "В космосе пахнет горячим металлом, жареным стейком и сваркой — так описывают запах астронавты.",
    "Мозг человека потребляет около 20% всей энергии тела, хотя его вес составляет лишь 2% от массы тела.",
    "Самая длинная живая система организмов на Земле — гриб Armillaria ostoyae в Орегоне, занимающий около 9 км².",
]

_FACTS_EN = [
    "Octopuses have three hearts, blue blood, and nine brains — one central and one in each tentacle.",
    "Honey never spoils. Archaeologists have found 3,000-year-old honey in Egyptian tombs — still edible.",
    "A banana is technically a berry, but a strawberry is not.",
    "The first computer bug was a literal insect. In 1947, a moth was found stuck in a Harvard computer relay and taped into a logbook.",
    "If you combined all the ants on Earth, they would weigh roughly as much as all the humans.",
    "Lightning strikes Earth about 100 times per second — roughly 8 million strikes a day.",
    "Oxford University is older than the Aztec Empire. Oxford was founded in 1096; the Aztec Empire in 1428.",
    "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
    "Your brain uses about 20% of your body's total energy, despite being only 2% of your body weight.",
    "Space smells like hot metal, burnt steak, and welding fumes — according to astronauts who have smelled it on their suits.",
    "A group of flamingos is called a flamboyance.",
    "The human body has enough iron to make a nail 3 inches long.",
    "Sharks are older than trees. Sharks have existed for around 450 million years; trees appeared about 350 million years ago.",
    "The inventor of the Pringles can is buried in one.",
]


def handler() -> str:
    is_en = getattr(config, "ACTIVE_LANGUAGE", "ru") == "en"
    return random.choice(_FACTS_EN if is_en else _FACTS_RU)