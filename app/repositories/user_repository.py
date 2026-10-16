import logging
from typing import Optional
from datetime import datetime
from app.database.connection import get_connection

logger = logging.getLogger(__name__)

async def create_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    """Створити нового користувача та повернути його ID"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, created_at, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (telegram_id, username, first_name, datetime.utcnow().isoformat())
        )
        await conn.commit()
        user_id = cursor.lastrowid
        logger.info(f"Створено нового користувача: telegram_id={telegram_id}, user_id={user_id}")
        return user_id

async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Отримати користувача за Telegram ID"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

async def get_user_id_by_telegram_id(telegram_id: int) -> Optional[int]:
    """Отримати внутрішній user_id за Telegram ID"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row['id']
        return None

async def update_user_activity(telegram_id: int, is_active: bool) -> None:
    """Оновити статус активності користувача"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET is_active = ? WHERE telegram_id = ?",
            (1 if is_active else 0, telegram_id)
        )
        await conn.commit()
