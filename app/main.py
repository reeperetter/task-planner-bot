"""Головний файл запуску бота."""

import asyncio
import logging
import os
import signal
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.database.migrations import run_migrations
from app.handlers import start, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_ping(request):
    """Обробник для UptimeRobot та перевірки здоров'я Render."""
    return web.Response(text="Bot is alive and polling!")


async def start_web_server():
    """Запускає веб-сервер, щоб Render бачив відкритий порт."""
    app = web.Application()
    app.router.add_get('/', handle_ping)
    
    port = int(os.getenv("PORT", 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Веб-сервер успішно запущено і тримає порт {port}")
    
    await asyncio.Event().wait()


async def main() -> None:
    logger.info("Ініціалізація бота...")
    await run_migrations()
    logger.info("База даних ініціалізовано")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(tasks.router)

    logger.info("Бот успішно запущено у режимі polling.")

    # ФУНКЦІЯ МИТТЄВОГО ВИМКНЕННЯ
    def handle_sigterm():
        logger.info("⚠️ Отримано сигнал завершення (SIGTERM). Миттєве вимкнення для уникнення конфлікту...")
        # Закриваємо сесію бота, щоб Telegram одразу звільнив токен
        asyncio.create_task(bot.session.close())
        sys.exit(0)

    # Реєструємо обробник сигналів від Render
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, handle_sigterm)
    loop.add_signal_handler(signal.SIGINT, handle_sigterm)

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            start_web_server()
        )
    except asyncio.CancelledError:
        logger.info("Роботу перервано")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
