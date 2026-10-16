import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from app.config import config

_db_path = Path(config.DATABASE_PATH)

@asynccontextmanager
async def get_connection():
    """Отримати асинхронне з'єднання з базою даних як контекстний менеджер"""
    conn = await aiosqlite.connect(_db_path)
    conn.row_factory = aiosqlite.Row
    # Увімкнення зовнішніх ключів
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()

async def init_db() -> None:
    """Ініціалізація бази даних: створення таблиць та міграції"""
    from app.database.migrations import run_migrations
    
    # Створюємо директорію для БД, якщо її немає
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Запускаємо міграції
    await run_migrations()
