"""Репозиторій для роботи із завданнями (PostgreSQL)."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.database.connection import get_connection

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
    """Створити нове завдання та повернути його ID."""
    # Перетворюємо рядки на datetime об'єкти
    due_at_dt = datetime.fromisoformat(due_at) if due_at else None
    due_date_dt = date.fromisoformat(due_date) if due_date else None
    
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks 
            (user_id, title, category, status, priority, due_at, due_date, 
             recurrence_rule_id, created_at, updated_at)
            VALUES ($1, $2, $3, 'in_progress', $4, $5, $6, $7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            user_id, title, category, priority, due_at_dt, due_date_dt, recurrence_rule_id
        )
        logger.info(f"Створено завдання: task_id={row['id']}, user_id={user_id}")
        return row['id']


async def get_task(task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Отримати завдання за ID з перевіркою власника."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tasks WHERE id = $1 AND user_id = $2",
            task_id, user_id
        )
        return dict(row) if row else None


async def get_tasks_for_date(user_id: int, target_date: date) -> List[Dict[str, Any]]:
    """Отримати завдання на конкретну дату."""
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND (
                due_date = $2
                OR (due_at >= $3 AND due_at <= $4)
              )
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, target_date, day_start, day_end
        )
        return [dict(row) for row in rows]


async def get_tasks_for_date_range(user_id: int, date_from: date, date_to: date) -> List[Dict[str, Any]]:
    """Отримати завдання в діапазоні дат."""
    day_start = datetime.combine(date_from, datetime.min.time())
    day_end = datetime.combine(date_to, datetime.max.time())
    
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND (
                (due_date >= $2 AND due_date <= $3)
                OR (due_at >= $4 AND due_at <= $5)
              )
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, date_from, date_to, day_start, day_end
        )
        return [dict(row) for row in rows]


async def get_planned_tasks(user_id: int) -> List[Dict[str, Any]]:
    """Отримати ЗАПЛАНОВАНІ завдання — сьогодні + майбутнє."""
    today = date.today()
    day_start = datetime.combine(today, datetime.min.time())
    
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND (
                due_date >= $2
                OR due_at >= $3
              )
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, today, day_start
        )
        return [dict(row) for row in rows]


async def get_done_tasks(user_id: int) -> List[Dict[str, Any]]:
    """Отримати ВИКОНАНІ завдання — ті, строк яких минув."""
    today = date.today()
    day_start = datetime.combine(today, datetime.min.time())
    
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND (
                due_date < $2
                OR due_at < $3
              )
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id, today, day_start
        )
        return [dict(row) for row in rows]


async def get_recurring_tasks(user_id: int) -> List[Dict[str, Any]]:
    """Отримати всі активні повторювані завдання користувача."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 
              AND status = 'in_progress'
              AND recurrence_rule_id IS NOT NULL
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def count_active_tasks_by_rule(rule_id: int) -> int:
    """Порахувати кількість активних завдань із цим правилом повторення."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM tasks WHERE recurrence_rule_id = $1 AND status = 'in_progress'",
            rule_id
        )
        return row['cnt'] if row else 0


async def get_tasks_without_due_date(user_id: int) -> List[Dict[str, Any]]:
    """Отримати активні завдання без жодного строку."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress'
              AND due_date IS NULL AND due_at IS NULL
            ORDER BY 
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END,
              created_at DESC
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def update_task(task_id: int, user_id: int, **kwargs) -> bool:
    """Оновити завдання."""
    logger.info(f"🔧 Виклик update_task: task_id={task_id}, user_id={user_id}, kwargs={kwargs}")
    
    if not kwargs:
        return False
    
    allowed_fields = {'title', 'category', 'status', 'priority', 'due_at', 'due_date', 'recurrence_rule_id', 'completed_at'}
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    # Конвертація рядків у об'єкти дат для asyncpg
    if 'due_at' in update_fields and isinstance(update_fields['due_at'], str):
        update_fields['due_at'] = datetime.fromisoformat(update_fields['due_at'])
    if 'due_date' in update_fields and isinstance(update_fields['due_date'], str):
        update_fields['due_date'] = date.fromisoformat(update_fields['due_date'])
    if 'completed_at' in update_fields and isinstance(update_fields['completed_at'], str):
        update_fields['completed_at'] = datetime.fromisoformat(update_fields['completed_at'])
        
    if not update_fields:
        logger.warning(f"⚠️ Спроба оновити недозволені поля: {kwargs.keys()}")
        return False
    
    set_clause = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(update_fields.keys()))
    values = list(update_fields.values()) + [task_id, user_id]
    
    query = f"UPDATE tasks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(values)-1} AND user_id = ${len(values)}"
    logger.info(f"🔧 SQL запит: {query}")
    logger.info(f"🔧 Параметри: {values}")
    
    async with get_connection() as conn:
        try:
            status = await conn.execute(query, *values)
            logger.info(f"🔧 Результат UPDATE з БД: {status}")
            return "UPDATE 1" in status
        except Exception as e:
            logger.error(f"🔧 КРИТИЧНА ПОМИЛКА SQL при оновленні: {e}", exc_info=True)
            return False


async def search_tasks(user_id: int, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Пошук завдань за текстом у назві (case-insensitive для PostgreSQL)."""
    search_pattern = f"%{query}%"
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tasks 
            WHERE user_id = $1 AND status = 'in_progress' AND title ILIKE $2
            ORDER BY 
              COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
              CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
            LIMIT $3
            """,
            user_id, search_pattern, limit
        )
        return [dict(row) for row in rows]


async def get_filtered_tasks(
    user_id: int, 
    category: Optional[str] = None, 
    priority: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Отримати завдання з фільтрацією за категорією або пріоритетом."""
    query = "SELECT * FROM tasks WHERE user_id = $1 AND status = 'in_progress'"
    params = [user_id]
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
        ORDER BY 
          COALESCE(due_at, CAST(due_date AS timestamp)) ASC,
          CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END
    """
    
    async with get_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def delete_task(task_id: int, user_id: int) -> bool:
    """Видалити завдання остаточно."""
    async with get_connection() as conn:
        status = await conn.execute(
            "DELETE FROM tasks WHERE id = $1 AND user_id = $2",
            task_id, user_id
        )
        return "DELETE 1" in status
