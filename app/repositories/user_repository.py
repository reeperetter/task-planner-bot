"""Репозиторій для роботи з користувачами (PostgreSQL)."""

import logging
from typing import Optional, Dict, Any
from app.database.connection import get_connection

logger = logging.getLogger(__name__)


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Отримати користувача за Telegram ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return dict(row) if row else None


async def get_user_id_by_telegram_id(telegram_id: int) -> Optional[int]:
    """Отримати ID користувача за Telegram ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return row['id'] if row else None


async def create_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    """Створити нового користувача та повернути його ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            telegram_id, username, first_name
        )
        logger.info(f"Створено нового користувача: telegram_id={telegram_id}, user_id={row['id']}")
        return row['id']
