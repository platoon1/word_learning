"""Загрузка переменных окружения приложения."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TEACHER_ID: int = int(os.getenv("TEACHER_ID", "0"))

# ALLOWED_STUDENT_IDS преобразуем в set[int]
_raw_students = os.getenv("ALLOWED_STUDENT_IDS", "")
ALLOWED_STUDENT_IDS: set[int] = {
    int(x.strip()) for x in _raw_students.split(",") if x.strip().isdigit()
}

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///korean_app.db")

API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))


def is_allowed_user(user_id: int) -> bool:
    """Проверка доступа: учитель или разрешённый ученик."""
    return user_id == TEACHER_ID or user_id in ALLOWED_STUDENT_IDS
