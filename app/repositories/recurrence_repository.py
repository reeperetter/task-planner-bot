"""Репозиторій для роботи з правилами повторення завдань (PostgreSQL)."""

import logging
from typing import Optional, List, Dict, Any
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
        row = await conn.fetchrow(
            """
            INSERT INTO recurrence_rules
            (rule_type, interval_days, days_of_week, day_of_month,
             execution_time, interval_months, interval_years, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            rule_type, interval_days, days_of_week, day_of_month,
            execution_time, interval_months, interval_years
        )
        logger.info(f"Створено правило повторення: id={row['id']}, type={rule_type}")
        return row['id']


async def get_rule(rule_id: int) -> Optional[Dict[str, Any]]:
    """Отримати правило за ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM recurrence_rules WHERE id = $1",
            rule_id
        )
        return dict(row) if row else None


async def get_rules_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Отримати всі правила повторення користувача через його активні завдання."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT rr.*
            FROM recurrence_rules rr
            JOIN tasks t ON t.recurrence_rule_id = rr.id
            WHERE t.user_id = $1 AND t.status = 'in_progress'
            ORDER BY rr.id DESC
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def delete_rule(rule_id: int) -> bool:
    """Видалити правило повторення."""
    async with get_connection() as conn:
        status = await conn.execute(
            "DELETE FROM recurrence_rules WHERE id = $1",
            rule_id
        )
        return "DELETE 1" in status
