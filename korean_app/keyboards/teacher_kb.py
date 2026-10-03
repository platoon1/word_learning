"""Inline-клавиатуры для учителя."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def approval_kb(topic_id: int) -> InlineKeyboardMarkup:
    """Кнопки одобрения/редактирования превью."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить", callback_data=f"approve:{topic_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ Редактировать", callback_data=f"edit:{topic_id}"
                ),
            ]
        ]
    )


def topics_select_kb(topic_ids: list[int], names: list[str]) -> InlineKeyboardMarkup:
    """Выбор существующей темы."""
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"topic:{tid}")]
        for tid, name in zip(topic_ids, names)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
