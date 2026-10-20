"""Модуль для виконання міграцій бази даних."""

import logging
from pathlib import Path
from app.database.connection import get_connection, init_db
from app.config import config

logger = logging.getLogger(__name__)

async def run_migrations() -> None:
    """Виконати міграції бази даних (автоматично вибирає PostgreSQL або SQLite)."""
    
    # Спочатку ініціалізуємо пул, якщо це PostgreSQL
    await init_db()
    
    # Визначаємо, яку схему використовувати
    if config.DATABASE_URL:
        schema_path = Path(__file__).parent / "schema_postgres.sql"
        logger.info("Використовується схема PostgreSQL (Neon)")
    else:
        schema_path = Path(__file__).parent / "schema_sqlite.sql"
        logger.info("Використовується схема SQLite (локальна)")
    
    if not schema_path.exists():
        logger.error(f"Файл схеми не знайдено: {schema_path}")
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    schema_sql = schema_path.read_text(encoding="utf-8")
    
    async with get_connection() as conn:
        try:
            if config.DATABASE_URL:
                # Для PostgreSQL розбиваємо SQL на окремі запити
                statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
                for statement in statements:
                    if statement:  # Пропускаємо порожні запити
                        await conn.execute(statement)
                logger.info("✅ Міграції PostgreSQL успішно виконано")
            else:
                # Для SQLite використовуємо executescript (виконує всі запити одразу)
                await conn.executescript(schema_sql)
                logger.info("✅ Міграції SQLite успішно виконано")
        except Exception as e:
            logger.error(f"Помилка під час міграції БД: {e}")
            raise
