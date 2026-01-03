import random


EVENTS = [
    {
        "text": "У вентиляції спалахнув вогонь. Дим і токсини вб'ють слабких першими.",
        "effect": "fire",
    },
    {
        "text": "Спалахнула хвороба. Тепер медичні навички — питання життя й смерті.",
        "effect": "disease",
    },
    {
        "text": "Саботаж систем життєзабезпечення. Хтось грає проти вас зсередини.",
        "effect": "sabotage",
    },
]


def random_event(rng: random.Random | None = None) -> dict:
    rng = rng or random
    return rng.choice(EVENTS)
