"""Репозиторій для роботи з налаштуваннями користувачів (PostgreSQL)."""

import logging
from typing import Optional, Dict, Any
from app.database.connection import get_connection

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "timezone": "Europe/Kyiv",
    "morning_report_time": "08:00",
    "morning_report_enabled": 1,
    "reminder_minutes_before": 60,
    "reminder_enabled": 1,
    "sort_order": "priority_desc,due_at_asc",
    "date_format": "%d.%m.%Y",
}


async def create_user_settings(user_id: int) -> None:
    """Створити стандартні налаштування для нового користувача."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (
                user_id, timezone, morning_report_time, morning_report_enabled,
                reminder_minutes_before, reminder_enabled, sort_order, date_format
            )
            VALUES ($1, 'Europe/Kyiv', '08:00', 1, 60, 1, 'priority_desc,due_at_asc', '%d.%m.%Y')
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id
        )
        logger.info(f"Створено налаштування для користувача user_id={user_id}")


async def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Отримати налаштування користувача (або створити стандартні, якщо відсутні)."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_settings WHERE user_id = $1",
            user_id
        )
        if row:
            result = {**DEFAULT_SETTINGS, **dict(row)}
            return result

    await create_user_settings(user_id)
    return {"user_id": user_id, **DEFAULT_SETTINGS}


async def update_user_settings(user_id: int, **kwargs) -> bool:
    """Оновити налаштування користувача."""
    if not kwargs:
        return False

    allowed_fields = {
        "timezone",
        "morning_report_time",
        "morning_report_enabled",
        "reminder_minutes_before",
        "reminder_enabled",
        "sort_order",
        "date_format",
    }
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not update_fields:
        logger.warning(f"Спроба оновити недозволені поля: {kwargs.keys()}")
        return False

    # Переконуємось, що запис налаштувань існує
    await get_user_settings(user_id)

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(update_fields.keys()))
    values = [user_id] + list(update_fields.values())

    query = f"UPDATE user_settings SET {set_clause} WHERE user_id = $1"

    async with get_connection() as conn:
        status = await conn.execute(query, *values)
        return "UPDATE 1" in status
