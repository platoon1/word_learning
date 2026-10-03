"""Общий LLM-провайдер для цепей (OpenRouter через LangChain ChatOpenAI).

ВАЖНО: ИИ используется ТОЛЬКО в трёх местах: word_parser, example_generator, example_editor.
"""
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
    )


def extract_json_array(text: str) -> list:
    """Достаёт JSON-массив из ответа LLM (устойчиво к markdown-обёрткам и лишнему тексту)."""
    text = text.strip()
    # Убираем ```json ... ``` обёртки
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # Пробуем прямой парсинг
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Ищем первый [...] блок
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Не удалось извлечь JSON-массив из ответа модели: {text[:200]}")
