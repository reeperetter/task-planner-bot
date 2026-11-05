import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.database.migrations import run_migrations
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.scheduler_service import SchedulerService

# Твої роутери
from app.handlers.start import router as start_router
from app.handlers.tasks import router as tasks_router

async def main():
    # Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    # Запуск міграцій бази даних перед стартом бота
    logging.info("Запуск міграцій бази даних...")
    await run_migrations()

    # Ініціалізація бота з використанням твоїх DefaultBotProperties та ParseMode
    bot = Bot(
        token=config.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Ініціалізація диспетчера з MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())

    # Підключення роутерів
    dp.include_router(start_router)
    dp.include_router(tasks_router)

    # Ініціалізація репозиторіїв бази даних
    task_repo = TaskRepository()
    user_repo = UserRepository()

    # Ініціалізація та запуск фонового планувальника нагадувань
    scheduler_service = SchedulerService(bot, task_repo, user_repo)
    scheduler_service.start()
    logging.info("Планувальник задач успішно запущено.")

    # Пропуск накопичених оновлень та старт polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        logging.info("Бот запущено в режимі polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardIncrement, SystemExit) if hasattr(asyncio, 'SystemExit') else (KeyboardInterrupt, SystemExit):
        logging.info("Роботу бота зупинено користувачем.")
