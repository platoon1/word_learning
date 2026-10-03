"""Проверка ответов ученика СТРОГО программной логикой (без ИИ).

Используется расстояние Левенштейна: допускается максимум 1 опечатка/изменение символа.
"""


def levenshtein_distance(s1: str, s2: str) -> int:
    """Классический динамический алгоритм расстояния Левенштейна."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalize(text: str) -> str:
    """Нормализация: trim + нижний регистр."""
    return text.strip().lower()


def check_with_levenshtein(student_answer: str, correct_answer: str, max_distance: int = 1) -> bool:
    """Проверка ответа с допуском max_distance изменений символа (по умолчанию 1 опечатка).

    НЕ использует ИИ — строго программная проверка.
    """
    a = normalize(student_answer)
    b = normalize(correct_answer)

    if a == b:
        return True

    return levenshtein_distance(a, b) <= max_distance
