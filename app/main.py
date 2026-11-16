import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.database.connection import close_db
from app.database.migrations import run_migrations
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.scheduler_service import SchedulerService

from app.handlers.start import router as start_router
from app.handlers.settings import router as settings_router
from app.handlers.tasks import router as tasks_router


async def _health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "task-planner-bot"})


async def _start_health_server() -> web.AppRunner | None:
    port_raw = os.getenv("PORT")
    if not port_raw:
        return None
    port = int(port_raw)
    web_app = web.Application()
    web_app.router.add_get("/", _health_handler)
    web_app.router.add_get("/health", _health_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logging.info(f"HTTP healthcheck-сервер запущено на 0.0.0.0:{port}")
    return runner


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Піднімаємо HTTP-порт якомога раніше, щоб Render Web Service зафіксував відкритий порт
    health_runner = await _start_health_server()

    logging.info("Запуск міграцій бази даних...")
    await run_migrations()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(tasks_router)

    task_repo = TaskRepository()
    user_repo = UserRepository()

    scheduler_service = SchedulerService(bot, task_repo, user_repo)
    scheduler_service.start()
    logging.info("Планувальник задач успішно запущено.")

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logging.info("Бот запущено в режимі polling...")
        await dp.start_polling(bot)
    finally:
        scheduler_service.shutdown()
        await bot.session.close()
        await close_db()
        if health_runner is not None:
            await health_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Роботу бота зупинено користувачем.")
