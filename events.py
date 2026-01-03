import random
from typing import Optional


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


def random_event(rng: Optional[random.Random] = None) -> dict:
    rng = rng or random
    return rng.choice(EVENTS)
