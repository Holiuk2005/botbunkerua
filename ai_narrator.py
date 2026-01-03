import json
import random
from dataclasses import dataclass
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


def _normalize_model(model: str) -> str:
    model = (model or "").strip()
    if not model:
        return model
    return model if model.startswith("models/") else f"models/{model}"


@dataclass(frozen=True)
class GeminiModel:
    name: str
    supported_methods: tuple[str, ...]


@dataclass(frozen=True)
class GeminiQuotaError(Exception):
    status_code: int
    message: str
    retry_after_s: Optional[int] = None
    raw: Optional[str] = None

    def __str__(self) -> str:
        base = f"Gemini quota/rate limit ({self.status_code}): {self.message}"
        if self.retry_after_s is not None:
            return f"{base} (retry_after={self.retry_after_s}s)"
        return base


def _parse_retry_after_seconds(error_json: dict) -> Optional[int]:
    details = error_json.get("error", {}).get("details") or []
    for d in details:
        if d.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
            delay = d.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return int(delay[:-1])
                except ValueError:
                    return None
    return None


async def list_gemini_models(*, api_key: str, timeout_s: float = 20.0) -> list[GeminiModel]:
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    params = {"key": api_key}

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Gemini models:list error {resp.status}: {text}")

    data = json.loads(text)
    models = []
    for m in data.get("models", []) or []:
        name = m.get("name")
        if not name:
            continue
        methods = tuple(m.get("supportedGenerationMethods", []) or [])
        models.append(GeminiModel(name=name, supported_methods=methods))
    return models


def pick_best_model(available: list[GeminiModel], preferred: Optional[str]) -> str:
    preferred_norm = _normalize_model(preferred or "") if preferred else ""

    def supports_generate(model: GeminiModel) -> bool:
        return "generateContent" in model.supported_methods

    available_generate = [m for m in available if supports_generate(m)]
    if not available_generate:
        raise RuntimeError("Gemini API: немає доступних моделей з методом generateContent")

    if preferred_norm:
        for m in available_generate:
            if m.name == preferred_norm:
                return m.name

    # Fallback order: try a few common model names if available, otherwise pick first.
    common = [
        "models/gemini-2.0-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-1.5-flash-latest",
        "models/gemini-1.5-pro-latest",
        "models/gemini-1.0-pro",
    ]
    names = {m.name for m in available_generate}
    for c in common:
        if c in names:
            return c

    return available_generate[0].name


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

    async def _call_generate(*, model_name: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
        params = {"key": api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, params=params, json=payload) as resp:
                text = await resp.text()
                if resp.status == 429:
                    try:
                        parsed = json.loads(text)
                    except Exception:
                        parsed = {}
                    retry_after = _parse_retry_after_seconds(parsed) if parsed else None
                    message = (
                        (parsed.get("error") or {}).get("message")
                        if isinstance(parsed, dict)
                        else None
                    )
                    raise GeminiQuotaError(
                        status_code=429,
                        message=message or "RESOURCE_EXHAUSTED",
                        retry_after_s=retry_after,
                        raw=text,
                    )
                if resp.status >= 400:
                    raise RuntimeError(f"Gemini API error {resp.status}: {text}")
        return text

    requested_model = _normalize_model(model)
    try:
        raw = await _call_generate(model_name=requested_model)
    except RuntimeError as err:
        # If model is not found/available for this key, auto-pick a valid one.
        msg = str(err)
        if " 404" in msg or "NOT_FOUND" in msg or "is not found" in msg:
            available = await list_gemini_models(api_key=api_key)
            picked = pick_best_model(available, preferred=model)
            raw = await _call_generate(model_name=picked)
        else:
            raise

    data = json.loads(raw)
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
