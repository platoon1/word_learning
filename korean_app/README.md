# 🇰🇷 Korean Mini App — Telegram Mini App для изучения корейского языка

Закрытая система для преподавателя и учеников: учитель загружает списки слов (текст или `.txt`), ИИ парсит их и генерирует контекстные примеры по уровню ученика (A1–B2), учитель одобряет материал, а ученики тренируются в Telegram Mini App (карточки, перевод, квиз, работа над ошибками).

## Ключевые принципы

- **ИИ (OpenRouter через LangChain) используется ТОЛЬКО в 3 местах**:
  1. Парсинг сырого списка слов (`chains/word_parser.py`)
  2. Генерация контекстных предложений по уровню (`chains/example_generator.py`)
  3. Редактирование примеров по текстовому запросу учителя (`chains/example_editor.py`)
- **Проверка ответов ученика — строго программная**, без ИИ: расстояние Левенштейна с допуском максимум 1 опечатку/изменение символа (`services/answer_checker.py`).
- **Закрытая система**: доступ имеют только `TEACHER_ID` и пользователи из `ALLOWED_STUDENT_IDS`. Остальные запросы блокируются middleware бота и возвращают `403` в API.

## Стек

Python 3.11+ · FastAPI · aiogram 3.x · LangChain (ChatOpenAI → OpenRouter) · SQLAlchemy 2.0 (async, aiosqlite) · Vanilla JS / HTML5 / CSS3 (Mini App — один файл `static/index.html`).

## Структура проекта

```text
korean_app/
├── .env                  # секреты и конфигурация (не коммитить)
├── .env.example          # шаблон .env
├── requirements.txt      # зависимости
├── config.py             # загрузка переменных окружения
├── database.py           # async engine и session (SQLAlchemy)
├── models.py             # ORM: User, Topic, Word, Assignment, ErrorWord
├── middleware.py         # aiogram-middleware проверки доступа
├── bot.py                # точка входа: aiogram + uvicorn (FastAPI) параллельно
├── api.py                # REST-эндпоинты для Mini App
├── chains/               # LangChain-цепи (только 3 разрешённые ИИ-задачи)
│   ├── _llm.py           # общий ChatOpenAI (OpenRouter) + извлечение JSON
│   ├── word_parser.py    # парсинг списка слов
│   ├── example_generator.py  # 3 примера на слово с учётом уровня
│   └── example_editor.py     # правка примеров по запросу учителя
├── services/             # бизнес-логика без ИИ
│   ├── answer_checker.py # check_with_levenshtein
│   └── session_service.py# сессии, пул ошибок, repeat delay
├── handlers/
│   ├── common.py         # /start, /add_student, /set_level
│   └── teacher.py        # /add_words, одобрение, редактирование
├── keyboards/teacher_kb.py  # inline-кнопки учителя
└── static/index.html     # фронтенд Telegram Mini App
```

## Установка зависимостей

Требуется **Python 3.11+**.

```bash
cd korean_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Конфигурация

Скопируйте шаблон и заполните значения:

```bash
cp .env.example .env
```

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `TEACHER_ID` | Telegram ID преподавателя (число) |
| `ALLOWED_STUDENT_IDS` | ID учеников через запятую, напр. `111111111,222222222` |
| `OPENROUTER_API_KEY` | Ключ API с [openrouter.ai](https://openrouter.ai) |
| `OPENROUTER_MODEL` | Модель, напр. `openai/gpt-4o-mini` |
| `DATABASE_URL` | По умолчанию `sqlite+aiosqlite:///korean_app.db` |
| `API_HOST` / `API_PORT` | Хост и порт FastAPI (по умолчанию `0.0.0.0:8000`) |

## Запуск

```bash
python bot.py
```

Одна команда запускает **параллельно**:
- long-polling бота aiogram;
- FastAPI (uvicorn) на `API_HOST:API_PORT`, который отдаёт Mini App (`GET /`) и API-эндпоинты.

База данных (SQLite) создаётся автоматически при первом старте.

### Подключение Mini App

1. Приложение должно быть доступно по публичному HTTPS-URL (tunnel: ngrok / cloudflared, либо деплой на сервер).
2. В [@BotFather]: `/newapp` (или «Bot Settings → Menu Button») → укажите URL вашего сервиса.
3. Ученики открывают Mini App через кнопку меню бота; `user_id` берётся из `Telegram.WebApp.initDataUnsafe`.

Для локальных тестов без Telegram можно открыть `http://localhost:8000/?user_id=<ID>` (ID должен быть в белом списке).

## Команды бота

**Преподаватель:**
- `/start` — справка;
- `/add_student <id> <имя> <уровень>` — добавить/обновить ученика (уровень: A1, A2, B1, B2);
- `/set_level <id> <уровень>` — сменить уровень;
- `/add_words` — мастер добавления слов: ID ученика (или `all`) → тема → текст или `.txt` со списком слов. ИИ парсит слова и генерирует примеры, учителю показывается превью с кнопками **[✅ Одобрить]** и **[✏️ Редактировать]**. После одобрения слова становятся доступны ученику (создаётся Assignment).

**Ученик:** `/start` возвращает «⛔ Доступ закрыт» — ученики пользуются только Mini App (доступен через кнопку меню бота, если их ID есть в `ALLOWED_STUDENT_IDS`). Сообщения посторонних пользователей игнорируются middleware.

## API для Mini App

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/` | Отдаёт `static/index.html` |
| GET | `/api/topics/{user_id}` | Темы ученика + кол-во слов и ошибок |
| POST | `/api/session/start` | `{user_id, topic_id, mode}` → `{session_id, words, total}` |
| POST | `/api/session/{session_id}/next` | Следующее слово или `{finished: true, stats}` |
| POST | `/api/answer/check` | Строгая проверка ответа (Левенштейн, допуск = 1) |
| POST | `/api/flashcard/answer` | `{user_id, word_id, knew}` → пул ошибок / correct_streak |

Режимы тренировки: `flashcards` (карточки), `translation` (перевод в контексте), `quiz` (квиз), `errors` (работа над ошибками).

## Логика работы над ошибками

- Неверный ответ → `ErrorWord.error_count += 1`, серия верных сбрасывается в 0.
- Слово удаляется из пула ошибок после **3 верных ответов подряд** (`correct_streak >= 3`).
- Повтор ошибки подмешивается раньше по расписанию: `calculate_repeat_delay(error_count) = min(total_words − 1, [10, 7, 5, 3, 2, 1][min(error_count − 1, 5)])`.

## Полезно знать

- `.env` содержит секреты — не коммитьте его (добавлен в `.gitignore`).
- Если `OPENROUTER_API_KEY` не задан, команды `/add_words` и редактирование вернут ошибку — остальная функциональность (тренировки, проверка ответов) работает без ИИ.
- Для продакшена замените SQLite на PostgreSQL (достаточно поменять `DATABASE_URL`) и поставьте `uvicorn` за reverse-proxy с HTTPS.
