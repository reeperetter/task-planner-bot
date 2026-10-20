"""Модуль для підключення до бази даних (гібридний: PostgreSQL або SQLite)."""

import logging
import asyncpg
import aiosqlite
from contextlib import asynccontextmanager
from app.config import config

logger = logging.getLogger(__name__)

# Глобальний пул з'єднань для PostgreSQL
postgres_pool: asyncpg.Pool | None = None

async def init_db():
    """Ініціалізація пулу з'єднань (тільки для PostgreSQL)."""
    global postgres_pool
    if config.DATABASE_URL:
        logger.info("Ініціалізація пулу з'єднань PostgreSQL (Neon)...")
        postgres_pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            server_settings={'jit': 'off'}  # Оптимізація для Neon
        )
        logger.info("✅ Пул з'єднань PostgreSQL успішно створено")
    else:
        logger.info("DATABASE_URL не знайдено. Використовується локальний SQLite.")

@asynccontextmanager
async def get_connection():
    """Надає з'єднання з БД залежно від конфігурації."""
    if config.DATABASE_URL:
        # Режим PostgreSQL (Neon)
        if postgres_pool is None:
            await init_db()
        async with postgres_pool.acquire() as conn:
            yield conn
    else:
        # Режим SQLite (локальна розробка)
        async with aiosqlite.connect(config.DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn
