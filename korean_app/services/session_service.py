"""Логика сессий: выбор слов, пул ошибок, repeat delay. Чистая бизнес-логика, без ИИ."""
import json
import random
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ErrorWord, Topic, Word, Assignment

# Задержки повторов в зависимости от количества ошибок (индекс = error_count - 1)
REPEAT_DELAYS = [10, 7, 5, 3, 2, 1]


def calculate_repeat_delay(error_count: int, total_words: int = 10_000_000) -> int:
    """Задержка повтора слова.

    Формула из ТЗ: min(total_words - 1, [10, 7, 5, 3, 2, 1][min(error_count - 1, 5)]).
    Если total_words не передан — используется большая заглушка (применяется только таблица задержек).
    """
    idx = min(max(error_count - 1, 0), 5)
    return min(total_words - 1, REPEAT_DELAYS[idx])


def _word_to_dict(word: Word, error_count: int = 0) -> dict:
    """Сериализация слова + первый пример для Mini App."""
    examples = []
    if word.examples_json:
        try:
            examples = json.loads(word.examples_json)
        except (json.JSONDecodeError, TypeError):
            examples = []
    example = examples[0] if examples else {}
    return {
        "id": word.id,
        "korean": word.korean,
        "russian": word.russian,
        "example_korean": example.get("korean", ""),
        "example_russian": example.get("russian", ""),
        "examples": examples,
        "error_count": error_count,
    }


async def get_session_words(
    db: AsyncSession,
    user_id: int,
    topic_id: int,
    mode: str,
    limit: Optional[int] = None,
) -> list[dict]:
    """Формирует список слов сессии.

    - mode == 'errors': слова из пула ошибок пользователя (по topic), сортировка по error_count DESC.
    - иначе: случайные approved=True слова темы.

    limit=None (по умолчанию) — берётся ВЕСЬ набор слов темы/ошибок (наборы небольшие).
    """
    if mode == "errors":
        stmt = (
            select(Word, ErrorWord.error_count)
            .join(ErrorWord, ErrorWord.word_id == Word.id)
            .where(ErrorWord.student_id == user_id, Word.topic_id == topic_id)
            .order_by(ErrorWord.error_count.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = (await db.execute(stmt)).all()
        return [_word_to_dict(w, ec) for w, ec in rows]

    stmt = select(Word).where(Word.topic_id == topic_id, Word.approved.is_(True))
    words = list((await db.execute(stmt)).scalars().all())
    random.shuffle(words)
    return [_word_to_dict(w) for w in (words[:limit] if limit is not None else words)]


async def add_to_error(db: AsyncSession, user_id: int, word_id: int) -> None:
    """Добавляет/увеличивает ошибку: error_count += 1, correct_streak = 0."""
    stmt = select(ErrorWord).where(ErrorWord.student_id == user_id, ErrorWord.word_id == word_id)
    err = (await db.execute(stmt)).scalar_one_or_none()
    if err is None:
        db.add(ErrorWord(student_id=user_id, word_id=word_id, error_count=1, correct_streak=0))
    else:
        err.error_count += 1
        err.correct_streak = 0
    await db.commit()


async def record_correct_answer(db: AsyncSession, user_id: int, word_id: int) -> None:
    """Увеличивает correct_streak; при streak >= 3 слово считается выученным и удаляется из пула ошибок."""
    stmt = select(ErrorWord).where(ErrorWord.student_id == user_id, ErrorWord.word_id == word_id)
    err = (await db.execute(stmt)).scalar_one_or_none()
    if err is None:
        return  # слова нет в пуле ошибок — нечего обновлять
    err.correct_streak += 1
    if err.correct_streak >= 3:
        await db.delete(err)
    await db.commit()


async def get_topics_for_student(db: AsyncSession, user_id: int) -> list[dict]:
    """Список тем ученика (через Assignment) с количествомapproved-слов и ошибок."""
    stmt = (
        select(Topic)
        .join(Assignment, Assignment.topic_id == Topic.id)
        .where(Assignment.student_id == user_id)
        .distinct()
    )
    topics = (await db.execute(stmt)).scalars().all()

    result = []
    for topic in topics:
        word_count = (
            await db.execute(
                select(Word.id).where(Word.topic_id == topic.id, Word.approved.is_(True))
            )
        ).scalars().all()
        error_count = (
            await db.execute(
                select(ErrorWord.id)
                .join(Word, Word.id == ErrorWord.word_id)
                .where(ErrorWord.student_id == user_id, Word.topic_id == topic.id)
            )
        ).scalars().all()
        result.append(
            {
                "id": topic.id,
                "name": topic.name,
                "word_count": len(word_count),
                "error_count": len(error_count),
            }
        )
    return result


async def get_word_by_id(db: AsyncSession, word_id: int) -> Optional[Word]:
    return (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
