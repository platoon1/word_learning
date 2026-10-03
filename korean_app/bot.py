"""Точка входа: совместный запуск aiogram-бота и uvicorn (FastAPI)."""
import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from api import app
from config import API_HOST, API_PORT, TELEGRAM_BOT_TOKEN
from database import init_db
from handlers import common, teacher
from middleware import register_access_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


async def on_startup(bot: Bot) -> None:
    await init_db()
    logger.info("БД инициализирована. Bot: @%s", (await bot.get_me()).username)


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в .env")

    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    register_access_middleware(dp)
    dp.include_router(common.router)
    dp.include_router(teacher.router)
    dp.startup.register(on_startup)

    # Запускаем бота и FastAPI параллельно
    server = uvicorn.Server(
        uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    )

    await asyncio.gather(
        bot.delete_webhook(drop_pending_updates=True),
        dp.start_polling(bot),
        server.serve(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка приложения.")
