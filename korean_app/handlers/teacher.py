"""Хендлеры учителя: /add_words (FSM), одобрение и редактирование примеров через ИИ-цепи.

ИИ используется ТОЛЬКО здесь: word_parser, example_generator, example_editor.
"""
import json
import logging
from dataclasses import dataclass, field

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from chains.example_editor import edit_examples
from chains.example_generator import generate_examples
from chains.word_parser import parse_words
from config import TEACHER_ID
from database import async_session_factory
from handlers.common import safe_answer
from keyboards.teacher_kb import approval_kb
from models import Assignment, Topic, User, Word

logger = logging.getLogger(__name__)
router = Router()


class AddWordsStates(StatesGroup):
    waiting_student = State()
    waiting_topic = State()
    waiting_words = State()


@dataclass
class PendingBatch:
    """Временное хранилище неподтверждённого пакета слов до одобрения учителем."""

    topic_id: int
    student_ids: list[int]
    level: str
    words: list[dict] = field(default_factory=list)  # [{'korean','russian','examples'}]


# pending batches по topic_id (до одобрения)
pending_batches: dict[int, PendingBatch] = {}


async def _read_words_file(message: Message) -> str | None:
    """Читает текст из .txt файла или из текста сообщения."""
    if message.document is not None:
        buffer = await message.bot.download(message.document)
        return buffer.read().decode("utf-8", errors="replace")
    return message.text


def _format_preview(batch: PendingBatch) -> str:
    lines = [f"📦 Предпросмотр (тема id={batch.topic_id}, уровень {batch.level}):\n"]
    for w in batch.words:
        lines.append(f"🇰🇷 {w['korean']} — 🇷🇺 {w['russian']}")
        for ex in w.get("examples", [])[:3]:
            lines.append(f"   • {ex['korean']}\n     ↳ {ex['russian']}")
        lines.append("")
    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n…"
    return text


async def _save_unapproved_words(db, batch: PendingBatch) -> None:
    """Сохраняет слова в БД с approved=False и examples_json."""
    for w in batch.words:
        db.add(
            Word(
                topic_id=batch.topic_id,
                korean=w["korean"],
                russian=w["russian"],
                examples_json=json.dumps(w.get("examples", []), ensure_ascii=False),
                approved=False,
            )
        )
    await db.commit()


@router.message(Command("add_words"))
async def cmd_add_words(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.from_user.id != TEACHER_ID:
        return
    await state.set_state(AddWordsStates.waiting_student)
    await safe_answer(message, "Кому назначаем? Введите ID ученика или 'all' (всем ученикам).")


@router.message(AddWordsStates.waiting_student, F.text)
async def step_student(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().lower()
    async with async_session_factory() as db:
        students = (await db.execute(select(User).where(User.role == "student"))).scalars().all()
        if raw == "all":
            student_ids = [s.id for s in students]
            level = students[0].language_level if students else "A1"
        else:
            try:
                sid = int(raw)
            except ValueError:
                await safe_answer(message, "Введите число (ID) или 'all'.")
                return
            student = next((s for s in students if s.id == sid), None)
            if student is None:
                await safe_answer(message, "Ученик не найден. Сначала /add_student.")
                return
            student_ids = [sid]
            level = student.language_level or "A1"

    await state.update_data(student_ids=student_ids, level=level)
    await state.set_state(AddWordsStates.waiting_topic)
    await safe_answer(message, "Введите название новой темы:")


@router.message(AddWordsStates.waiting_topic, F.text)
async def step_topic(message: Message, state: FSMContext) -> None:
    topic_name = (message.text or "").strip()
    if not topic_name:
        await safe_answer(message, "Название не может быть пустым.")
        return
    async with async_session_factory() as db:
        topic = Topic(name=topic_name, teacher_id=TEACHER_ID)
        db.add(topic)
        await db.commit()
        await db.refresh(topic)
    await state.update_data(topic_id=topic.id)
    await state.set_state(AddWordsStates.waiting_words)
    await safe_answer(message, "Теперь пришлите список слов (текстом или .txt файлом).")


@router.message(AddWordsStates.waiting_words, F.text.as_(None) & F.document)
async def step_words_document(message: Message, state: FSMContext) -> None:
    await _process_words(message, state)


async def _process_words(message: Message, state: FSMContext) -> None:
    raw_text = await _read_words_file(message)
    if not raw_text or not raw_text.strip():
        await safe_answer(message, "Не удалось прочитать список слов. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    topic_id = data["topic_id"]
    level = data["level"]
    student_ids = data["student_ids"]

    await safe_answer(message, "🤖 Парсю список слов…")
    try:
        parsed = await parse_words(raw_text)
    except Exception as e:  # noqa: BLE001
        logger.exception("word_parser failed")
        await safe_answer(message, f"❌ Ошибка парсинга: {e}")
        return
    if not parsed:
        await safe_answer(message, "❌ Не удалось извлечь ни одной пары слов. Проверьте формат.")
        return

    await safe_answer(message, f"✅ Распознано {len(parsed)} слов. Генерирую примеры (уровень {level})…")
    try:
        enriched = await generate_examples(parsed, level)
    except Exception as e:  # noqa: BLE001
        logger.exception("example_generator failed")
        await safe_answer(message, f"❌ Ошибка генерации примеров: {e}")
        return

    batch = PendingBatch(topic_id=topic_id, student_ids=student_ids, level=level, words=enriched)
    pending_batches[topic_id] = batch

    async with async_session_factory() as db:
        await _save_unapproved_words(db, batch)

    await state.clear()
    await safe_answer(message, _format_preview(batch), reply_markup=approval_kb(topic_id))


@router.callback_query(F.data.startswith("edit:"))
async def cb_edit(callback: CallbackQuery, state: FSMContext) -> None:
    topic_id = int(callback.data.split(":", 1)[1])
    if topic_id not in pending_batches:
        await callback.answer("Пакет уже одобрен или утерян.", show_alert=True)
        return
    await state.set_state(AddWordsStates.waiting_words)
    await state.update_data(edit_topic_id=topic_id)
    await safe_answer(callback.message, "Опишите текстом, что исправить в примерах:")
    await callback.answer()


@router.message(AddWordsStates.waiting_words, F.text)
async def step_words_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    # Если находимся в режиме редактирования пакета — применяем правки через example_editor
    if data.get("edit_topic_id") in pending_batches:
        await apply_edit(message, state)
        return
    await _process_words(message, state)


async def apply_edit(message: Message, state: FSMContext) -> None:
    """Обработка текстового запроса учителя на редактирование (вызывает цепь example_editor)."""
    data = await state.get_data()
    topic_id = data.get("edit_topic_id")
    request_text = (message.text or "").strip()
    if not request_text or request_text.startswith("/"):
        await safe_answer(message, "Опишите правки обычным текстом.")
        return

    batch = pending_batches[topic_id]
    await safe_answer(message, "✏️ Редактирую примеры…")
    try:
        updated = await edit_examples(batch.words, request_text, batch.level)
    except Exception as e:  # noqa: BLE001
        logger.exception("example_editor failed")
        await safe_answer(message, f"❌ Ошибка редактирования: {e}")
        return

    batch.words = updated
    # Обновляем examples_json в БД
    async with async_session_factory() as db:
        rows = (
            await db.execute(select(Word).where(Word.topic_id == topic_id, Word.approved.is_(False)))
        ).scalars().all()
        by_korean = {w["korean"]: w for w in updated}
        for row in rows:
            if row.korean in by_korean:
                row.examples_json = json.dumps(by_korean[row.korean].get("examples", []), ensure_ascii=False)
        await db.commit()

    await state.clear()
    await safe_answer(message, _format_preview(batch), reply_markup=approval_kb(topic_id))


@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(callback: CallbackQuery) -> None:
    topic_id = int(callback.data.split(":", 1)[1])
    batch = pending_batches.pop(topic_id, None)

    async with async_session_factory() as db:
        # Ставим approved=True всем словам темы
        rows = (
            await db.execute(select(Word).where(Word.topic_id == topic_id))
        ).scalars().all()
        for row in rows:
            row.approved = True

        # Создаём Assignment для выбранных учеников
        student_ids = batch.student_ids if batch else []
        for sid in student_ids:
            exists = (
                await db.execute(
                    select(Assignment).where(Assignment.topic_id == topic_id, Assignment.student_id == sid)
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(Assignment(topic_id=topic_id, student_id=sid))
        await db.commit()

    n_words = len(rows)
    await safe_answer(callback.message,
        f"✅ Тема одобрена! Слов: {n_words}. Назначено ученикам: {len(student_ids)}."
    )
    await callback.answer()
