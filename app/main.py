import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.database.connection import init_db
from app.handlers import start, tasks

async def main() -> None:
    # Налаштування базового логування
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Ініціалізація бота...")

    # Ініціалізація БД
    await init_db()
    logger.info("База даних ініціалізовано")

    # Створюємо DefaultBotProperties
    default_props = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=config.BOT_TOKEN, default=default_props)
    
    # Створюємо MemoryStorage для FSM
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Підключення роутерів
    dp.include_router(start.router)
    dp.include_router(tasks.router)

    logger.info("Бот успішно запущено у режимі polling.")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено користувачем.")
