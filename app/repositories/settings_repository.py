"""Репозиторій для роботи з налаштуваннями користувачів (PostgreSQL)."""

import logging
from typing import Optional, Dict, Any
from app.database.connection import get_connection

logger = logging.getLogger(__name__)


async def create_user_settings(user_id: int) -> None:
    """Створити стандартні налаштування для нового користувача."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, timezone, morning_report_time, sort_order, date_format)
            VALUES ($1, 'Europe/Kyiv', '07:00', 'priority_desc,due_at_asc', '%d.%m.%Y')
            """,
            user_id
        )
        logger.info(f"Створено налаштування для користувача user_id={user_id}")


async def get_user_settings(user_id: int) -> Optional[Dict[str, Any]]:
    """Отримати налаштування користувача."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_settings WHERE user_id = $1",
            user_id
        )
        return dict(row) if row else None


async def update_user_settings(user_id: int, **kwargs) -> bool:
    """Оновити налаштування користувача."""
    if not kwargs:
        return False
    
    allowed_fields = {'timezone', 'morning_report_time', 'sort_order', 'date_format'}
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_fields:
        logger.warning(f"Спроба оновити недозволені поля: {kwargs.keys()}")
        return False
    
    # Формуємо SET clause з параметрами $2, $3 і т.д. (бо $1 це user_id)
    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(update_fields.keys()))
    values = [user_id] + list(update_fields.values())
    
    query = f"UPDATE user_settings SET {set_clause} WHERE user_id = $1"
    
    async with get_connection() as conn:
        status = await conn.execute(query, *values)
        return "UPDATE 1" in status
