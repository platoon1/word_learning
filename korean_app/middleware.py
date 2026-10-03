"""Aiogram middleware для проверки доступа (закрытая система).

Доступ имеют только TEACHER_ID и пользователи из ALLOWED_STUDENT_IDS.
Все остальные сообщения игнорируются.
"""
from typing import Any, Awaitable, Callable

from aiogram import Dispatcher
from aiogram.types import CallbackQuery, Message

from config import is_allowed_user


class AccessCheckMiddleware:
    """Пропускает только учителя и разрешённых учеников. Остальные — молча игнорируются."""

    async def __call__(
        self,
        handler: Callable[[Any], Awaitable[None]],
        event: Message | CallbackQuery,
        data: dict,
    ) -> None:
        # aiogram 3.x: у Message/CallbackQuery есть from_user (alias поля "from")
        user = getattr(event, "from_user", None)
        if user is None:
            update = data.get("event_update")
            user = getattr(update, "effective_user", None) if update is not None else None

        if user is not None and is_allowed_user(user.id):
            await handler(event, data)
        # Иначе — не вызываем handler: запрос блокируется


def register_access_middleware(dp: Dispatcher) -> None:
    dp.message.middleware(AccessCheckMiddleware())
    dp.callback_query.middleware(AccessCheckMiddleware())
