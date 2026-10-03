"""Цепь №3: редактирование сгенерированных предложений по неформальному текстовому запросу преподавателя."""
import json

from langchain_core.prompts import ChatPromptTemplate

from chains._llm import extract_json_array, get_llm

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Отредактируй примеры для слов на основе запроса: '{edit_request}'. "
            "Текущие данные: {current_data}. Сохраняй уровень {level}. "
            "Верни обновленный JSON массив в том же формате: каждый элемент содержит поля "
            "korean, russian и examples (examples — массив объектов с полями korean и russian).",
        ),
        ("human", "Выполни редактирование и верни только JSON."),
    ]
)


async def edit_examples(current_data: list[dict], edit_request: str, level: str = "A1") -> list[dict]:
    """Редактирует примеры слов по текстовому запросу учителя.

    Args:
        current_data: текущий JSON [{'korean','russian','examples':[...]}, ...].
        edit_request: неформальное текстовое описание правок.
        level: уровень ученика (сохранять его).
    """
    llm = get_llm(temperature=0.3)
    chain = PROMPT | llm
    result = await chain.ainvoke(
        {
            "edit_request": edit_request,
            "current_data": json.dumps(current_data, ensure_ascii=False),
            "level": level,
        }
    )
    return extract_json_array(result.content)
