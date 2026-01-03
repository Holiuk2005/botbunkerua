import asyncio
import logging
from html import escape
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import Message

from characters import format_character, generate_character
from config import BOT_TOKEN, GEMINI_API_KEY, GEMINI_MODEL, NARRATOR
from ai_narrator import GeminiQuotaError, generate_cataclysm_story, pick_default_cataclysm_topic
from events import random_event
from game import Game

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# games[chat_id] = Game
GAMES: Dict[int, Game] = {}

# Simple anti-spam for expensive AI calls (per chat)
_LAST_AI_CALL_AT: Dict[int, float] = {}
_AI_COOLDOWN_S: float = 30.0


def _ai_rate_limited(chat_id: int) -> float:
    now = asyncio.get_running_loop().time()
    last = _LAST_AI_CALL_AT.get(chat_id, 0.0)
    wait = _AI_COOLDOWN_S - (now - last)
    return wait


def _mark_ai_call(chat_id: int) -> None:
    _LAST_AI_CALL_AT[chat_id] = asyncio.get_running_loop().time()


def _fallback_cataclysm_text() -> str:
    # Uses the legacy event list as a simple, offline fallback.
    event = random_event()
    return event["text"]


def is_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def is_private(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


async def is_chat_admin(message: Message) -> bool:
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)


def get_game(chat_id: int) -> Game:
    game = GAMES.get(chat_id)
    if game is None:
        game = Game(chat_id=chat_id)
        GAMES[chat_id] = game
    return game


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if is_private(message):
        await message.answer(
            f"<b>{NARRATOR}:</b> Це приватний канал. Тут ти отримуєш свого персонажа.\n\n"
            "У групі: /newgame → /join → /startgame → /round"
        )
        return

    await message.answer(
        f"<b>{NARRATOR}:</b> На Землі — кінець. Є бункер, але місць лише на половину.\n"
        "Гра йде в групі. Персонажі — тільки в приват.\n\n"
        "Команди:\n"
        "/newgame — створити нову гру (адмін чату)\n"
        "/join — приєднатися\n"
        "/startgame — почати гру (адмін)\n"
        "/round — почати раунд і відкрити голосування (адмін)\n"
        "/vote @username — проголосувати\n"
        "/endround — завершити голосування й вибити одного (адмін)\n"
        "/status — стан гри\n"
        "/endgame — завершити гру (адмін)"
    )


@dp.message(Command("newgame"))
async def cmd_newgame(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> /newgame працює лише в групі.")
        return
    if not await is_chat_admin(message):
        await message.answer(f"<b>{NARRATOR}:</b> Тільки адмін чату може створювати гру.")
        return

    game = get_game(message.chat.id)
    game.new_game(message.from_user.id)
    await message.answer(
        f"<b>{NARRATOR}:</b> ☢️ Створено гру «Бункер». Напишіть /join.\n"
        "Кожен гравець має відкрити приват із ботом і натиснути Start — інакше персонаж не прийде."
    )

    # AI narrator intro (silent fallback to legacy events)
    story: str
    if not GEMINI_API_KEY:
        story = _fallback_cataclysm_text()
        await message.answer(f"<b>{NARRATOR}:</b>\n{escape(story)}")
        return

    if _ai_rate_limited(message.chat.id) > 0:
        story = _fallback_cataclysm_text()
        await message.answer(f"<b>{NARRATOR}:</b>\n{escape(story)}")
        return

    topic = pick_default_cataclysm_topic()
    try:
        _mark_ai_call(message.chat.id)
        story = await generate_cataclysm_story(
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
            cataclysm_type=topic,
        )
    except (GeminiQuotaError, Exception):
        story = _fallback_cataclysm_text()
    await message.answer(f"<b>{NARRATOR}:</b>\n{escape(story)}")


@dp.message(Command("join"))
async def cmd_join(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> Приєднання — лише в групі, де йде гра.")
        return

    game = get_game(message.chat.id)
    if game.started:
        await message.answer(f"<b>{NARRATOR}:</b> Набір закритий. Гра вже стартувала.")
        return

    tg_username = message.from_user.username
    if not tg_username:
        await message.answer(
            f"<b>{NARRATOR}:</b> Для голосування потрібен Telegram username.\n"
            "Увімкни username в налаштуваннях Telegram і повтори /join."
        )
        return

    char = generate_character()
    try:
        game.join(message.from_user.id, tg_username, char)
    except RuntimeError as err:
        await message.answer(f"<b>{NARRATOR}:</b> {err}")
        return

    # Send secret character in private
    try:
        await bot.send_message(
            message.from_user.id,
            f"<b>{NARRATOR}:</b> 🧬 Твій персонаж:\n\n{format_character(char)}\n\n"
            "Це таємниця. Не зливай у групу. Працюй словами й фактами.",
        )
        await message.answer(f"<b>{NARRATOR}:</b> @{tg_username} приєднався(лась). Персонаж надісланий у приват.")
    except TelegramForbiddenError:
        await message.answer(
            f"<b>{NARRATOR}:</b> @{tg_username}, я не можу написати тобі в приват.\n"
            "Відкрий приват із ботом, натисни Start і повтори /join."
        )


@dp.message(Command("startgame"))
async def cmd_startgame(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> /startgame можливий лише в групі.")
        return
    if not await is_chat_admin(message):
        await message.answer(f"<b>{NARRATOR}:</b> Тільки адмін чату може стартувати гру.")
        return

    game = get_game(message.chat.id)
    try:
        game.start_game(message.from_user.id)
    except (RuntimeError, PermissionError) as err:
        await message.answer(f"<b>{NARRATOR}:</b> {err}")
        return

    await message.answer(
        f"<b>{NARRATOR}:</b> Гра стартувала. Місць у бункері: <b>{game.bunker_capacity()}</b>.\n"
        "Далі: /round"
    )


@dp.message(Command("round"))
async def cmd_round(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> Раунди проводяться лише в групі.")
        return
    if not await is_chat_admin(message):
        await message.answer(f"<b>{NARRATOR}:</b> /round запускає лише адмін чату.")
        return

    game = get_game(message.chat.id)
    try:
        game.start_round(message.from_user.id)
    except (RuntimeError, PermissionError) as err:
        await message.answer(f"<b>{NARRATOR}:</b> {err}")
        return

    event = random_event()
    await message.answer(
        f"<b>{NARRATOR}:</b> 🔔 Раунд {game.round}\n\n"
        f"{event['text']}\n\n"
        "🗳️ Голосування відкрито. Команда: /vote @username"
    )


@dp.message(Command("cataclysm"))
async def cmd_cataclysm(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer(f"<b>{NARRATOR}:</b> Формат: /cataclysm <тема>")
        return

    topic = parts[1].strip()

    # Silent fallback to legacy events when Gemini is unavailable/limited.
    if not GEMINI_API_KEY or _ai_rate_limited(message.chat.id) > 0:
        story = _fallback_cataclysm_text()
        await message.answer(f"<b>{NARRATOR}:</b>\n{escape(story)}")
        return

    try:
        _mark_ai_call(message.chat.id)
        story = await generate_cataclysm_story(
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
            cataclysm_type=topic,
        )
    except (GeminiQuotaError, Exception):
        story = _fallback_cataclysm_text()

    await message.answer(f"<b>{NARRATOR}:</b>\n{escape(story)}")


@dp.message(Command("vote"))
async def cmd_vote(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> Голосування — лише в групі.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(f"<b>{NARRATOR}:</b> Формат: /vote @username")
        return

    game = get_game(message.chat.id)
    ok = False
    try:
        ok = game.vote(message.from_user.id, parts[1])
    except RuntimeError as err:
        await message.answer(f"<b>{NARRATOR}:</b> {err}")
        return

    if not ok:
        await message.answer(
            f"<b>{NARRATOR}:</b> Ціль не знайдена серед живих. Переконайся, що гравець має username і він у грі."
        )
        return

    await message.answer(f"<b>{NARRATOR}:</b> Голос прийнято.")


@dp.message(Command("endround"))
async def cmd_endround(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> /endround можливий лише в групі.")
        return
    if not await is_chat_admin(message):
        await message.answer(f"<b>{NARRATOR}:</b> /endround запускає лише адмін чату.")
        return

    game = get_game(message.chat.id)
    eliminated = game.eliminate_player()
    if eliminated is None:
        await message.answer(f"<b>{NARRATOR}:</b> Немає голосів. Виживання без рішень — теж рішення.")
        return

    await message.answer(
        f"<b>{NARRATOR}:</b> 💀 @{eliminated.username} вибуває.\n"
        f"Професія: {eliminated.character.get('profession', 'невідомо')}"
    )

    if game.is_finished():
        survivors = game.alive_players()
        text = "<b>🚪 Двері бункера зачиняються…</b>\n\n<b>ВИЖИЛИ:</b>\n"
        for p in survivors:
            text += f"• @{p.username} — {p.character.get('profession', 'невідомо')}\n"
        text += "\nЛюдство отримало шанс. Питання — чи ви ним скористаєтесь."
        await message.answer(text)
        GAMES.pop(game.chat_id, None)


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> Статус дивляться в групі.")
        return

    game = get_game(message.chat.id)
    await message.answer(f"<b>{NARRATOR}:</b>\n{game.status_text()}")


@dp.message(Command("endgame"))
async def cmd_endgame(message: Message) -> None:
    if not is_group(message):
        await message.answer(f"<b>{NARRATOR}:</b> /endgame можливий лише в групі.")
        return
    if not await is_chat_admin(message):
        await message.answer(f"<b>{NARRATOR}:</b> Тільки адмін чату може завершити гру.")
        return

    game = get_game(message.chat.id)
    game.end_game()
    GAMES.pop(message.chat.id, None)
    await message.answer(f"<b>{NARRATOR}:</b> Гру завершено. Щоб почати заново: /newgame")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
