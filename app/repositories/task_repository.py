"""Репозиторій для роботи із завданнями (PostgreSQL)."""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from app.database.connection import get_connection
from app.utils.dates import today_kyiv, to_kyiv_naive

logger = logging.getLogger(__name__)


async def create_task(
    user_id: int,
    title: str,
    category: str = "personal",
    priority: str = "normal",
    due_at: Optional[str] = None,
    due_date: Optional[str] = None,
    recurrence_rule_id: Optional[int] = None,
) -> int:
    due_at_dt = to_kyiv_naive(datetime.fromisoformat(due_at)) if due_at else None
    due_date_dt = date.fromisoformat(due_date) if due_date else None
    now = to_kyiv_naive()

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks 
            (user_id, title, category, status, priority, due_at, due_date, 
             recurrence_rule_id, created_at, updated_at)
            VALUES ($1, $2, $3, 'in_progress', $4, $5, $6, $7, $8, $8)
            RETURNING id
            """,
            user_id, title, category, priority, due_at_dt, due_date_dt, recurrence_rule_id, now
        )
        logger.info(f"Створено завдання: task_id={row['id']}, user_id={user_id}")
        return row["id"]


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1 AND user_id = $2", task_id, user_id)
        return dict(row) if row else None


async def get_tasks_for_date(user_id: int, target_date: date) -> List[Dict[str, Any]]:
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND (due_date = $2 OR (due_at >= $3 AND due_at <= $4))
            ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                     CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, target_date, day_start, day_end
        )
        return [dict(row) for row in rows]


async def get_tasks_for_date_range(user_id: int, date_from: date, date_to: date) -> List[Dict[str, Any]]:
    day_start = datetime.combine(date_from, datetime.min.time())
    day_end = datetime.combine(date_to, datetime.max.time())
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND ((due_date >= $2 AND due_date <= $3) OR (due_at >= $4 AND due_at <= $5))
            ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                     CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, date_from, date_to, day_start, day_end
        )
        return [dict(row) for row in rows]


async def get_planned_tasks(user_id: int) -> List[Dict[str, Any]]:
    today = today_kyiv()
    day_start = datetime.combine(today, datetime.min.time())
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress' AND (due_date >= $2 OR due_at >= $3)
            ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                     CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, today, day_start
        )
        return [dict(row) for row in rows]


async def get_done_tasks(user_id: int) -> List[Dict[str, Any]]:
    """Отримати виконані завдання (status = 'completed')."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'completed'
            ORDER BY COALESCE(completed_at, updated_at) DESC, id DESC
            LIMIT 50
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def get_recurring_tasks(user_id: int) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks
            WHERE user_id = $1 AND status = 'in_progress' AND recurrence_rule_id IS NOT NULL
            ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                     CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def count_active_tasks_by_rule(rule_id: int) -> int:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM tasks WHERE recurrence_rule_id = $1 AND status = 'in_progress'",
            rule_id
        )
        return row["cnt"] if row else 0


async def get_tasks_without_due_date(user_id: int) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks
            WHERE user_id = $1 AND status = 'in_progress' AND due_date IS NULL AND due_at IS NULL
            ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END, created_at DESC
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def update_task(task_id: int, user_id: int, **kwargs) -> bool:
    if not kwargs:
        return False

    allowed_fields = {
        "title", "category", "status", "priority",
        "due_at", "due_date", "recurrence_rule_id", "completed_at", "notified_at"
    }
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not update_fields:
        logger.warning(f"⚠️ Спроба оновити недозволені поля: {kwargs.keys()}")
        return False

    if "due_date" in update_fields and isinstance(update_fields["due_date"], str):
        try:
            update_fields["due_date"] = datetime.strptime(update_fields["due_date"], "%Y-%m-%d").date()
        except ValueError:
            pass
    if "due_at" in update_fields and isinstance(update_fields["due_at"], str):
        try:
            update_fields["due_at"] = to_kyiv_naive(datetime.fromisoformat(update_fields["due_at"]))
        except ValueError:
            pass
    if ("due_at" in update_fields or "due_date" in update_fields) and "notified_at" not in update_fields:
        update_fields["notified_at"] = None
    if "completed_at" in update_fields and isinstance(update_fields["completed_at"], str):
        try:
            update_fields["completed_at"] = to_kyiv_naive(datetime.fromisoformat(update_fields["completed_at"]))
        except ValueError:
            pass

    now = to_kyiv_naive()
    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(update_fields.keys()))
    values = list(update_fields.values()) + [now, task_id, user_id]

    query = f"""
        UPDATE tasks 
        SET {set_clause}, updated_at = ${len(values)-2}
        WHERE id = ${len(values)-1} AND user_id = ${len(values)}
    """

    async with get_connection() as conn:
        try:
            status = await conn.execute(query, *values)
            logger.info(f"✅ UPDATE успішний: {status} (task_id={task_id})")
            return "UPDATE 1" in status
        except Exception as e:
            logger.error(f"❌ SQL ПОМИЛКА UPDATE: {e} | Query: {query} | Values: {values}", exc_info=True)
            return False


async def search_tasks(user_id: int, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    search_pattern = f"%{query}%"
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks
            WHERE user_id = $1 AND status = 'in_progress' AND title ILIKE $2
            ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                     CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            LIMIT $3
            """,
            user_id, search_pattern, limit
        )
        return [dict(row) for row in rows]


async def get_filtered_tasks(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tasks WHERE user_id = $1 AND status = 'in_progress'"
    params: list[Any] = [user_id]
    param_idx = 2
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                 CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_tasks_for_date_filtered(user_id: int, target_date: date, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    query = """
        SELECT * FROM tasks 
        WHERE user_id = $1 AND status = 'in_progress' AND (due_date = $2 OR (due_at >= $3 AND due_at <= $4))
    """
    params: list[Any] = [user_id, target_date, day_start, day_end]
    param_idx = 5
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                 CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_tasks_for_date_range_filtered(user_id: int, date_from: date, date_to: date, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    day_start = datetime.combine(date_from, datetime.min.time())
    day_end = datetime.combine(date_to, datetime.max.time())
    query = """
        SELECT * FROM tasks 
        WHERE user_id = $1 AND status = 'in_progress' AND ((due_date >= $2 AND due_date <= $3) OR (due_at >= $4 AND due_at <= $5))
    """
    params: list[Any] = [user_id, date_from, date_to, day_start, day_end]
    param_idx = 6
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                 CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_planned_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    today = today_kyiv()
    day_start = datetime.combine(today, datetime.min.time())
    query = """
        SELECT * FROM tasks 
        WHERE user_id = $1 AND status = 'in_progress' AND (due_date >= $2 OR due_at >= $3)
    """
    params: list[Any] = [user_id, today, day_start]
    param_idx = 4
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                 CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_done_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    """Отримати виконані завдання (status = 'completed') з фільтрацією."""
    query = "SELECT * FROM tasks WHERE user_id = $1 AND status = 'completed'"
    params: list[Any] = [user_id]
    param_idx = 2
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(completed_at, updated_at) DESC, id DESC
        LIMIT 50
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_recurring_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tasks WHERE user_id = $1 AND status = 'in_progress' AND recurrence_rule_id IS NOT NULL"
    params: list[Any] = [user_id]
    param_idx = 2
    if category:
        query += f" AND category = ${param_idx}"
        params.append(category)
        param_idx += 1
    if priority:
        query += f" AND priority = ${param_idx}"
        params.append(priority)
        param_idx += 1
    query += """
        ORDER BY COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
                 CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def delete_task(task_id: int, user_id: int) -> bool:
    async with get_connection() as conn:
        status = await conn.execute("DELETE FROM tasks WHERE id = $1 AND user_id = $2", task_id, user_id)
        return "DELETE 1" in status


# =============================================================================
# ФУНКЦІЇ ДЛЯ НАГАДУВАНЬ ТА РАНКОВИХ ЗВІТІВ (з урахуванням налаштувань користувача)
# =============================================================================

async def get_upcoming_reminders() -> List[Dict[str, Any]]:
    """
    Отримати завдання, про які треба нагадати згідно з індивідуальним налаштуванням
    користувача `reminder_minutes_before` (стандартно 60 хв).
    """
    now = to_kyiv_naive()
    query = """
        SELECT t.id, t.title, t.due_at, t.priority, t.category, t.user_id,
               u.telegram_id,
               COALESCE(s.reminder_minutes_before, 60) AS reminder_minutes_before
        FROM tasks t
        JOIN users u ON t.user_id = u.id
        LEFT JOIN user_settings s ON s.user_id = u.id
        WHERE t.status = 'in_progress'
          AND u.is_active = 1
          AND COALESCE(s.reminder_enabled, 1) = 1
          AND COALESCE(s.reminder_minutes_before, 60) > 0
          AND t.due_at IS NOT NULL
          AND t.due_at >= $1
          AND t.due_at <= $1 + (COALESCE(s.reminder_minutes_before, 60) * INTERVAL '1 minute')
          AND (
              t.notified_at IS NULL
              OR t.notified_at < t.due_at - (COALESCE(s.reminder_minutes_before, 60) * INTERVAL '1 minute')
          )
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query, now)
        return [dict(row) for row in rows]


async def mark_task_notified(task_id: int) -> bool:
    """Позначити завдання як таке, про яке вже нагадали."""
    now = to_kyiv_naive()
    query = """
        UPDATE tasks 
        SET notified_at = $1 
        WHERE id = $2
    """
    async with get_connection() as conn:
        status = await conn.execute(query, now, task_id)
        return "UPDATE 1" in status


async def was_morning_report_sent(user_id: int, report_date: date) -> bool:
    """Перевірити, чи вже надсилався ранковий дайджест користувачу за вказану дату."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM report_log
            WHERE user_id = $1 AND report_date = $2 AND status = 'success'
            """,
            user_id, report_date
        )
        return row is not None


async def log_morning_report(
    user_id: int,
    report_date: date,
    status: str = "success",
    error_message: Optional[str] = None,
) -> None:
    """Зафіксувати результат відправки ранкового дайджесту в report_log (ідемпотентно)."""
    now = to_kyiv_naive()
    success_time = now if status == "success" else None
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO report_log (user_id, report_date, attempt_time, status, success_time, error_message)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, report_date, status)
            DO UPDATE SET attempt_time = EXCLUDED.attempt_time,
                          success_time = COALESCE(EXCLUDED.success_time, report_log.success_time),
                          error_message = EXCLUDED.error_message
            """,
            user_id, report_date, now, status, success_time, error_message
        )


class TaskRepository:
    """ООП-обгортка над функціями репозиторію для сумісності зі SchedulerService."""

    async def get_tasks_by_date(self, user_id: int, target_date: date) -> List[Dict[str, Any]]:
        return await get_tasks_for_date(user_id, target_date)

    async def get_tasks_without_due_date(self, user_id: int) -> List[Dict[str, Any]]:
        return await get_tasks_without_due_date(user_id)

    async def get_upcoming_reminders(self) -> List[Dict[str, Any]]:
        return await get_upcoming_reminders()

    async def mark_as_reminded(self, task_id: int) -> bool:
        return await mark_task_notified(task_id)

    async def was_morning_report_sent(self, user_id: int, report_date: date) -> bool:
        return await was_morning_report_sent(user_id, report_date)

    async def log_morning_report(
        self,
        user_id: int,
        report_date: date,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        await log_morning_report(user_id, report_date, status, error_message)
