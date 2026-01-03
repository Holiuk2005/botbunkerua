import random


PROFESSIONS = [
    "Лікар",
    "Інженер",
    "Військовий",
    "Фермер",
    "Психолог",
    "Механік",
]

HEALTH = [
    "Здоровий",
    "Хронічна хвороба",
    "Свіжа травма",
    "Астма",
]

HOBBIES = [
    "Виживання",
    "Ремонт",
    "Медицина",
    "Радіозв'язок",
    "Заготівля їжі",
]

PHOBIAS = [
    "Клаустрофобія",
    "Немає",
    "Паніка в натовпі",
    "Боязнь темряви",
]

BAGGAGE = [
    "Аптечка",
    "Інструменти",
    "Фільтр для води",
    "Рація",
    "Насіння",
]

SECRETS = [
    "Безплідний",
    "Геній",
    "Прихована хвороба",
    "Схильний до саботажу",
    "Незламна психіка",
]


def generate_character(rng: random.Random | None = None) -> dict:
    rng = rng or random
    return {
        "profession": rng.choice(PROFESSIONS),
        "health": rng.choice(HEALTH),
        "hobby": rng.choice(HOBBIES),
        "phobia": rng.choice(PHOBIAS),
        "baggage": rng.choice(BAGGAGE),
        "secret": rng.choice(SECRETS),
    }


def format_character(char: dict) -> str:
    return (
        f"Професія: {char['profession']}\n"
        f"Здоровʼя: {char['health']}\n"
        f"Хобі: {char['hobby']}\n"
        f"Фобія: {char['phobia']}\n"
        f"Багаж: {char['baggage']}\n"
        f"Секрет: {char['secret']}"
    )
