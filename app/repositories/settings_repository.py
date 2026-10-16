import logging
from typing import Optional
from app.database.connection import get_connection

logger = logging.getLogger(__name__)

async def create_user_settings(user_id: int) -> None:
    """Створити стандартні налаштування для нового користувача"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, timezone, morning_report_time, sort_order, date_format)
            VALUES (?, 'Europe/Kyiv', '07:00', 'priority_desc,due_at_asc', '%d.%m.%Y')
            """,
            (user_id,)
        )
        await conn.commit()
        logger.info(f"Створено налаштування для користувача user_id={user_id}")

async def get_user_settings(user_id: int) -> Optional[dict]:
    """Отримати налаштування користувача"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

async def update_user_settings(user_id: int, **kwargs) -> None:
    """Оновити налаштування користувача"""
    if not kwargs:
        return
    
    allowed_fields = {'timezone', 'morning_report_time', 'sort_order', 'date_format'}
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_fields:
        logger.warning(f"Спроба оновити недозволені поля: {kwargs.keys()}")
        return
    
    set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
    values = list(update_fields.values()) + [user_id]
    
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE user_settings SET {set_clause} WHERE user_id = ?",
            values
        )
        await conn.commit()
        logger.info(f"Оновлено налаштування для користувача user_id={user_id}: {update_fields}")
