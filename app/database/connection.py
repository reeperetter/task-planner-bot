"""Модуль для підключення до бази даних (гібридний: PostgreSQL або SQLite)."""

import logging
import asyncpg
import aiosqlite
from contextlib import asynccontextmanager
from app.config import config

logger = logging.getLogger(__name__)

# Глобальний пул з'єднань для PostgreSQL
postgres_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Ініціалізація пулу з'єднань (тільки для PostgreSQL)."""
    global postgres_pool
    if config.DATABASE_URL and postgres_pool is None:
        logger.info("Ініціалізація пулу з'єднань PostgreSQL (Neon)...")
        postgres_pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            max_inactive_connection_lifetime=60.0,
            command_timeout=30.0,
            server_settings={"jit": "off"},  # Оптимізація для Neon
        )
        logger.info("✅ Пул з'єднань PostgreSQL успішно створено")
    elif not config.DATABASE_URL:
        logger.info("DATABASE_URL не знайдено. Використовується локальний SQLite.")


async def close_db() -> None:
    """Коректне закриття пулу з'єднань при зупинці бота."""
    global postgres_pool
    if postgres_pool is not None:
        await postgres_pool.close()
        postgres_pool = None
        logger.info("Пул з'єднань PostgreSQL закрито.")


@asynccontextmanager
async def get_connection():
    """Надає з'єднання з БД залежно від конфігурації."""
    if config.DATABASE_URL:
        if postgres_pool is None:
            await init_db()
        async with postgres_pool.acquire() as conn:
            yield conn
    else:
        async with aiosqlite.connect(config.DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn
