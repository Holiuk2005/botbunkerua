import json
import random
from typing import Optional

import aiohttp


DEFAULT_CATASTLYSM_TOPICS = [
    "глобальна біоепідемія зі зривом систем охорони здоровʼя",
    "обмежений ядерний обмін із подальшою ядерною зимою",
    "каскадні відмови енергосистем і тривала техногенна криза",
    "різка зміна клімату з колапсом аграрного виробництва",
    "масштабна хімічна аварія з отруєнням води та ґрунтів",
]


def pick_default_cataclysm_topic(rng: Optional[random.Random] = None) -> str:
    rng = rng or random
    return rng.choice(DEFAULT_CATASTLYSM_TOPICS)


def build_cataclysm_prompt(cataclysm_type: str) -> str:
    return (
        "META-PROMPT ДЛЯ GEMINI\n"
        "(Генерація вступних історій гри «Бункер»)\n"
        "Ти — Ведучий настільної гри «Бункер».\n\n"
        "Твоє завдання — створювати вступні історії катаклізму\n"
        "перед початком гри.\n\n"
        "ОБОВʼЯЗКОВІ ПРАВИЛА:\n"
        "- Мова: українська\n"
        "- Стиль: серйозний, сухий, офіційний, постапокаліптичний\n"
        "- Без діалогів\n"
        "- Без художніх прикрас і пафосу\n"
        "- Без ролеплею\n"
        "- Без звернення до гравців\n"
        "- Без гумору\n"
        "- Без нових ігрових правил\n"
        "- Не оцінювати людей чи їхні рішення\n\n"
        "СТРУКТУРА ІСТОРІЇ:\n"
        "1. Початок катастрофи (коли і як усе почалося)\n"
        "2. Механізм руйнування (хвороба, війна, клімат, технологія тощо)\n"
        "3. Глобальні наслідки для планети\n"
        "4. Усвідомлення безвиході людством\n"
        "5. Чисельність населення, що вижило (реалістичне число)\n\n"
        "ФОРМАТ:\n"
        "- Суцільний текст\n"
        "- Абзаци по 2–4 речення\n"
        "- Обʼєм: 180–300 слів\n\n"
        "ЗАБОРОНЕНО:\n"
        "- Казкові елементи\n"
        "- Містика\n"
        "- Супергерої\n"
        "- Особисті історії окремих персонажів\n\n"
        f"ТЕМА КАТАКЛІЗМУ:\n{cataclysm_type}\n\n"
        "Почни текст одразу з опису катастрофи."
    )


async def generate_cataclysm_story(
    *,
    api_key: str,
    model: str,
    cataclysm_type: str,
    timeout_s: float = 30.0,
) -> str:
    prompt = build_cataclysm_prompt(cataclysm_type)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ]
    }

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, params=params, json=payload) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Gemini API error {resp.status}: {text}")

    data = json.loads(text)
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini API: порожня відповідь")

    content = (candidates[0].get("content") or {})
    parts = content.get("parts") or []
    if not parts:
        raise RuntimeError("Gemini API: немає тексту у відповіді")

    out_text: Optional[str] = parts[0].get("text")
    if not out_text:
        raise RuntimeError("Gemini API: порожній текст")

    return out_text.strip()
