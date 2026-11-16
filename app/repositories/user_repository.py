"""Репозиторій для роботи з користувачами (PostgreSQL)."""

import logging
from typing import Optional, Dict, Any, List
from app.database.connection import get_connection
from app.utils.dates import to_kyiv_naive

logger = logging.getLogger(__name__)


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Отримати користувача за Telegram ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Отримати користувача за внутрішнім ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
        return dict(row) if row else None


async def get_user_id_by_telegram_id(telegram_id: int) -> Optional[int]:
    """Отримати ID користувача за Telegram ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return row["id"] if row else None


async def get_all_active_users() -> List[Dict[str, Any]]:
    """Отримати всіх активних користувачів разом із налаштуваннями."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT u.*, COALESCE(s.timezone, 'Europe/Kyiv') AS timezone,
                   COALESCE(s.morning_report_time, '08:00') AS morning_report_time
            FROM users u
            LEFT JOIN user_settings s ON s.user_id = u.id
            WHERE u.is_active = 1
            """
        )
        return [dict(row) for row in rows]


async def create_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    """Створити нового користувача та повернути його ID."""
    now = to_kyiv_naive()
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name, created_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            telegram_id, username, first_name, now
        )
        logger.info(f"Створено нового користувача: telegram_id={telegram_id}, user_id={row['id']}")
        return row["id"]


class UserRepository:
    """ООП-обгортка для сумісності з сервісами та планувальником."""

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        return await get_user_by_telegram_id(telegram_id)

    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await get_user_by_id(user_id)

    async def get_all_users(self) -> List[Dict[str, Any]]:
        return await get_all_active_users()

    async def create(self, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> int:
        return await create_user(telegram_id, username, first_name)
