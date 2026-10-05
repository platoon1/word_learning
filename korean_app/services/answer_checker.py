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


PUNCT_TABLE = str.maketrans(
    {
        "«": "", "»": "", '"': "", "'": "", "’": "", "`": "",
        ",": " ", ";": " ", ":": " ", "!": " ", "?": " ", ".": " ",
        "(": " ", ")": " ", "-": " ", "–": " ", "—": " ",
    }
)


def normalize(text: str) -> str:
    """Нормализация: trim + нижний регистр."""
    return text.strip().lower()


def _normalize_words(text: str) -> list[str]:
    """Плотная нормализация для сравнения по словам.

    Нижний регистр, удаление пунктуации (в т.ч. дефиса), сжатие пробелов.
    """
    cleaned = text.lower().translate(PUNCT_TABLE)
    return [w for w in cleaned.split() if w]


def _first_word_ok(answer_words: list[str], correct_words: list[str]) -> bool:
    """Эвристика «первого слова»: ответ засчитывается, если первое слово ответа
    точно совпадает с первым словом правильного перевода и длиннее 2 букв
    (порог отсекает предлоги/союзы: «в», «на», «и», «не» и т.п.).

    Используется только когда расстояние Левенштейна по всей строке слишком велико
    (например, правильный ответ «хочется чего-то, тянуть на что-то», а ученик
    написал «хочется что-то»).
    """
    if not answer_words or not correct_words:
        return False
    first = answer_words[0]
    return len(first) > 2 and first == correct_words[0]


def check_with_levenshtein(
    student_answer: str,
    correct_answer: str,
    max_distance: int = 1,
    allow_first_word: bool = True,
) -> bool:
    """Проверка ответа БЕЗ ИИ — строго программная.

    Порядок:
    1. Точное совпадение (после нормализации) -> True.
    2. Расстояние Левенштейна <= max_distance (допуск 1 опечатки) -> True.
    3. Если allow_first_word и первое слово ответа (>2 букв, чтобы не засчитывать
       предлоги) точно совпадает с первым словом правильного перевода -> True.
       Это позволяет shorter-варианты длинных переводов («хочется что-то» при
       эталоне «хочется чего-то, тянуть на что-то») считать верными.
    """
    a = normalize(student_answer)
    b = normalize(correct_answer)

    if not a:
        return False

    if a == b:
        return True

    if levenshtein_distance(a, b) <= max_distance:
        return True

    if allow_first_word:
        return _first_word_ok(_normalize_words(a), _normalize_words(b))

    return False
