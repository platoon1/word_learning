"""Цепь №1: парсинг сырого списка слов от преподавателя (текст или .txt)."""
from langchain_core.prompts import ChatPromptTemplate

from chains._llm import extract_json_array, get_llm

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Ты парсер. Извлеки пары 'корейское слово - русский перевод' из текста. "
            "Игнорируй мусор. Верни ТОЛЬКО JSON массив, где каждый элемент — объект "
            "с полями korean и russian.",
        ),
        ("human", "{raw_text}"),
    ]
)


async def parse_words(raw_text: str) -> list[dict]:
    """Разбирает сырой список слов в [{'korean': ..., 'russian': ...}, ...]."""
    llm = get_llm(temperature=0.0)
    chain = PROMPT | llm
    result = await chain.ainvoke({"raw_text": raw_text})
    return extract_json_array(result.content)
