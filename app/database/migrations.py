import logging
from pathlib import Path
from app.database.connection import get_connection

logger = logging.getLogger(__name__)

async def run_migrations() -> None:
    """Виконати всі необхідні міграції бази даних"""
    schema_path = Path(__file__).parent / "schema.sql"
    
    if not schema_path.exists():
        logger.error(f"Файл схеми не знайдено: {schema_path}")
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    async with get_connection() as conn:
        try:
            # Читаємо та виконуємо SQL-схему
            schema_sql = schema_path.read_text(encoding="utf-8")
            await conn.executescript(schema_sql)
            await conn.commit()
            logger.info("Міграції бази даних успішно виконано")
        except Exception as e:
            logger.error(f"Помилка під час міграції БД: {e}")
            raise
