"""Головний файл запуску бота."""

import asyncio
import logging
import os

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
    """Запускає веб-сервер, щоб Render бачив відкритий порт і не вбивав процес."""
    app = web.Application()
    app.router.add_get('/', handle_ping)
    
    # Render автоматично передає змінну PORT. Ми використовуємо 10000 як надійний фолбек.
    port = int(os.getenv("PORT", 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Веб-сервер успішно запущено і тримає порт {port}")
    
    # Цей рядок критично важливий для Render: він не дає функції завершитися
    await asyncio.Event().wait()


async def main() -> None:
    logger.info("Ініціалізація бота...")
    
    await run_migrations()
    logger.info("База даних ініціалізовано")

    # ВИПРАВЛЕНО: новий синтаксис для aiogram 3.7.0+
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(tasks.router)

    logger.info("Бот успішно запущено у режимі polling.")

    try:
        # Запускаємо обидва процеси паралельно і назавжди
        await asyncio.gather(
            dp.start_polling(bot),
            start_web_server()
        )
    except asyncio.CancelledError:
        logger.info("Отримано сигнал завершення роботи")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
