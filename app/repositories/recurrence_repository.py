"""Репозиторій для роботи з правилами повторення завдань."""

import logging
from typing import Optional, List
from datetime import datetime
from app.database.connection import get_connection

logger = logging.getLogger(__name__)


async def create_rule(
    rule_type: str,
    interval_days: Optional[int] = None,
    days_of_week: Optional[str] = None,
    day_of_month: Optional[int] = None,
    execution_time: Optional[str] = None,
    interval_months: Optional[int] = None,
    interval_years: Optional[int] = None,
) -> int:
    """Створити нове правило повторення та повернути його ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO recurrence_rules
            (rule_type, interval_days, days_of_week, day_of_month,
             execution_time, interval_months, interval_years, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_type,
                interval_days,
                days_of_week,
                day_of_month,
                execution_time,
                interval_months,
                interval_years,
                datetime.utcnow().isoformat(),
            ),
        )
        await conn.commit()
        rule_id = cursor.lastrowid
        logger.info(f"Створено правило повторення: id={rule_id}, type={rule_type}")
        return rule_id


async def get_rule(rule_id: int) -> Optional[dict]:
    """Отримати правило за ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM recurrence_rules WHERE id = ?",
            (rule_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_rules_for_user(user_id: int) -> List[dict]:
    """Отримати всі правила повторення користувача через його активні завдання."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT DISTINCT rr.*
            FROM recurrence_rules rr
            JOIN tasks t ON t.recurrence_rule_id = rr.id
            WHERE t.user_id = ? AND t.status = 'in_progress'
            ORDER BY rr.id DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_rule(rule_id: int) -> bool:
    """Видалити правило повторення."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "DELETE FROM recurrence_rules WHERE id = ?",
            (rule_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0
