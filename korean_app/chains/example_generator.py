"""Цепь №2: генерация контекстных предложений для слов с учётом уровня ученика (A1-B2)."""
from langchain_core.prompts import ChatPromptTemplate

from chains._llm import extract_json_array, get_llm

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Ты преподаватель корейского. Уровень ученика: {level}. "
            "Для каждого слова создай 3 простых предложения (5-10 слов) с этим словом и переводом. "
            "Используй лексику не выше {level}. "
            "Верни JSON массив, где каждый элемент содержит поля korean, russian и examples "
            "(examples — массив объектов с полями korean и russian).",
        ),
        ("human", "Слова:\n{words_json}"),
    ]
)


async def generate_examples(words: list[dict], level: str = "A1") -> list[dict]:
    """Генерирует по 3 примера для каждого слова.

    Args:
        words: [{'korean': ..., 'russian': ...}, ...] — результат word_parser.
        level: уровень ученика (A1, A2, B1, B2).

    Returns:
        [{'korean': ..., 'russian': ..., 'examples': [{'korean':..., 'russian':...}, ...]}, ...]
    """
    import json

    llm = get_llm(temperature=0.4)
    chain = PROMPT | llm
    result = await chain.ainvoke(
        {"level": level, "words_json": json.dumps(words, ensure_ascii=False)}
    )
    return extract_json_array(result.content)
