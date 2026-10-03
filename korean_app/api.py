"""FastAPI роуты для Telegram Mini App.

ВАЖНО: проверка ответов ученика здесь выполняется СТРОГО программно
(check_with_levenshtein), без вызовов LLM.
"""
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import is_allowed_user
from database import get_session
from services.answer_checker import check_with_levenshtein
from services.session_service import (
    add_to_error,
    get_session_words,
    get_topics_for_student,
    get_word_by_id,
    record_correct_answer,
)

app = FastAPI(title="Korean Mini App API")

STATIC_DIR = Path(__file__).parent / "static"

# Хранилище активных сессий: session_id -> {user_id, topic_id, mode, words, index}
active_sessions: dict[str, dict] = {}


class SessionStart(BaseModel):
    user_id: int
    topic_id: int
    mode: str  # flashcards | translation | quiz | errors
    limit: int = 10


class AnswerCheck(BaseModel):
    user_id: int
    word_id: int
    answer: str
    direction: str = "ko_to_ru"  # ko_to_ru | ru_to_ko
    mode: Optional[str] = None


class FlashcardAnswer(BaseModel):
    user_id: int
    word_id: int
    knew: bool


def _check_access(user_id: int) -> None:
    if not is_allowed_user(user_id):
        raise HTTPException(status_code=403, detail="Доступ запрещён")


@app.get("/")
async def index() -> str:
    """Отдаёт frontend Mini App."""
    html_file = STATIC_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="index.html не найден")
    return (html_file).read_text(encoding="utf-8")


@app.get("/api/topics/{user_id}")
async def api_topics(user_id: int, db: AsyncSession = Depends(get_session)) -> dict:
    _check_access(user_id)
    topics = await get_topics_for_student(db, user_id)
    return {"topics": topics}


@app.post("/api/session/start")
async def api_session_start(payload: SessionStart, db: AsyncSession = Depends(get_session)) -> dict:
    _check_access(payload.user_id)
    words = await get_session_words(
        db, payload.user_id, payload.topic_id, payload.mode, limit=payload.limit
    )
    session_id = uuid.uuid4().hex
    active_sessions[session_id] = {
        "user_id": payload.user_id,
        "topic_id": payload.topic_id,
        "mode": payload.mode,
        "words": words,
        "index": 0,
        "stats": {"correct": 0, "incorrect": 0},
    }
    return {"session_id": session_id, "words": words, "total": len(words)}


@app.post("/api/session/{session_id}/next")
async def api_session_next(session_id: str, db: AsyncSession = Depends(get_session)) -> dict:
    session = active_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    _check_access(session["user_id"])

    words = session["words"]
    idx = session["index"]
    if idx >= len(words):
        total = len(words)
        correct = session["stats"]["correct"]
        incorrect = session["stats"]["incorrect"]
        active_sessions.pop(session_id, None)
        return {
            "finished": True,
            "stats": {
                "correct": correct,
                "incorrect": incorrect,
                "total": total,
                "percent": round((correct / total) * 100) if total else 0,
            },
        }

    session["index"] = idx + 1
    return {"finished": False, "word": words[idx]}


@app.post("/api/answer/check")
async def api_answer_check(payload: AnswerCheck, db: AsyncSession = Depends(get_session)) -> dict:
    """Проверка ответа — строго через расстояние Левенштейна, БЕЗ ИИ."""
    _check_access(payload.user_id)
    word = await get_word_by_id(db, payload.word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Слово не найдено")

    examples = []
    try:
        examples = json.loads(word.examples_json or "[]")
    except json.JSONDecodeError:
        examples = []

    # Определяем ожидаемый ответ и пример по направлению
    example = examples[0] if examples else {}
    if payload.direction == "ru_to_ko":
        correct_answer = word.korean
    else:
        correct_answer = word.russian

    correct = check_with_levenshtein(payload.answer, correct_answer, max_distance=1)

    if correct:
        await record_correct_answer(db, payload.user_id, word.id)
    else:
        await add_to_error(db, payload.user_id, word.id)

    return {"correct": correct, "correct_answer": correct_answer}


@app.post("/api/flashcard/answer")
async def api_flashcard_answer(payload: FlashcardAnswer, db: AsyncSession = Depends(get_session)) -> dict:
    _check_access(payload.user_id)
    word = await get_word_by_id(db, payload.word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Слово не найдено")

    if payload.knew:
        await record_correct_answer(db, payload.user_id, word.id)
    else:
        await add_to_error(db, payload.user_id, word.id)

    return {"ok": True}
