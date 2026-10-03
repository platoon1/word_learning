"""Общие хендлеры: /start, /add_student, /set_level (только для учителя)."""
from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select

from config import TEACHER_ID
from database import async_session_factory
from models import User

router = Router()

VALID_LEVELS = {"A1", "A2", "B1", "B2"}


async def safe_answer(message: Message, text: str, **kwargs) -> None:
    """Отвечает в plain-text.

    В bot.py глобально включён parse_mode=HTML, но тексты команд содержат
    '<id>', '<уровень>' и текст ошибок ИИ с '<...>' — Telegram не может это
    распарсить (Bad Request: can't parse entities). Явный parse_mode=None
    отключает разметку для конкретного сообщения. Если ответ всё равно не
    прошёл — повторяем без kwargs, чтобы не ронять обработчик апдейта.
    """
    try:
        await message.answer(text, parse_mode=None, **kwargs)
    except TelegramAPIError:
        await message.answer(text[:4000])


def _is_teacher(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == TEACHER_ID


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _is_teacher(message):
        await safe_answer(message, "⛔ Доступ закрыт. Обратитесь к преподавателю.")
        return
    await safe_answer(message,
        "👋 Привет, преподаватель!\n\n"
        "Команды:\n"
        "/add_student <id> <имя> <уровень> — добавить ученика\n"
        "/set_level <id> <уровень> — сменить уровень\n"
        "/add_words — загрузить список слов (ИИ распарсит и сгенерирует примеры)"
    )


@router.message(Command("add_student"))
async def cmd_add_student(message: Message) -> None:
    if not _is_teacher(message):
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await safe_answer(message, "Формат: /add_student <telegram_id> <имя> <уровень A1|A2|B1|B2>")
        return
    try:
        student_id = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID ученика должен быть числом.")
        return
    name = parts[2]
    level = parts[3].strip().upper()
    if level not in VALID_LEVELS:
        await safe_answer(message, f"Неверный уровень. Допустимо: {', '.join(sorted(VALID_LEVELS))}")
        return

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
        if user is None:
            db.add(User(id=student_id, role="student", name=name, language_level=level))
        else:
            user.name = name
            user.language_level = level
            user.role = "student"
        await db.commit()
    await safe_answer(message, f"✅ Ученик {name} (id={student_id}, уровень {level}) сохранён.")


@router.message(Command("set_level"))
async def cmd_set_level(message: Message) -> None:
    if not _is_teacher(message):
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await safe_answer(message, "Формат: /set_level <telegram_id> <уровень>")
        return
    try:
        student_id = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID ученика должен быть числом.")
        return
    level = parts[2].strip().upper()
    if level not in VALID_LEVELS:
        await safe_answer(message, f"Неверный уровень. Допустимо: {', '.join(sorted(VALID_LEVELS))}")
        return

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
        if user is None:
            await safe_answer(message, "Ученик не найден. Сначала /add_student.")
            return
        user.language_level = level
        await db.commit()
    await safe_answer(message, f"✅ Уровень ученика (id={student_id}) изменён на {level}.")
