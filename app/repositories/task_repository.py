import logging
from typing import Optional, List
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
    recurrence_rule_id: Optional[int] = None
) -> int:
    """Створити нове завдання та повернути його ID"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO tasks 
            (user_id, title, category, status, priority, due_at, due_date, 
             recurrence_rule_id, created_at, updated_at)
            VALUES (?, ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, category, priority, due_at, due_date, 
             recurrence_rule_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        await conn.commit()
        task_id = cursor.lastrowid
        logger.info(f"Створено завдання: task_id={task_id}, user_id={user_id}")
        return task_id

async def get_task(task_id: int, user_id: int) -> Optional[dict]:
    """Отримати завдання за ID з перевіркою власника"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

async def get_tasks_by_filter(
    user_id: int,
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    due_date_from: Optional[str] = None,
    due_date_to: Optional[str] = None,
    due_at_from: Optional[str] = None,
    due_at_to: Optional[str] = None,
    has_due_date: Optional[bool] = None,
    limit: int = 50
) -> List[dict]:
    """Отримати список завдань за фільтрами"""
    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [user_id]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    
    if due_date_from:
        query += " AND due_date >= ?"
        params.append(due_date_from)
    
    if due_date_to:
        query += " AND due_date <= ?"
        params.append(due_date_to)
    
    if due_at_from:
        query += " AND due_at >= ?"
        params.append(due_at_from)
    
    if due_at_to:
        query += " AND due_at <= ?"
        params.append(due_at_to)
    
    if has_due_date is not None:
        if has_due_date:
            query += " AND (due_date IS NOT NULL OR due_at IS NOT NULL)"
        else:
            query += " AND due_date IS NULL AND due_at IS NULL"
    
    query += " ORDER BY priority DESC, due_at ASC, due_date ASC LIMIT ?"
    params.append(limit)
    
    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_tasks_without_due_date(user_id: int) -> List[dict]:
    """Отримати активні завдання без жодного строку"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM tasks 
            WHERE user_id = ? AND status = 'in_progress'
              AND due_date IS NULL AND due_at IS NULL
            ORDER BY priority DESC, created_at DESC
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def update_task(task_id: int, user_id: int, **kwargs) -> bool:
    """Оновити завдання"""
    if not kwargs:
        return False
    
    allowed_fields = {
        'title', 'category', 'status', 'priority', 'due_at', 'due_date', 
        'recurrence_rule_id', 'completed_at'
    }
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_fields:
        logger.warning(f"Спроба оновити недозволені поля: {kwargs.keys()}")
        return False
    
    update_fields['updated_at'] = datetime.utcnow().isoformat()
    
    set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
    values = list(update_fields.values()) + [task_id, user_id]
    
    async with get_connection() as conn:
        cursor = await conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ? AND user_id = ?",
            values
        )
        await conn.commit()
        return cursor.rowcount > 0

async def delete_task(task_id: int, user_id: int) -> bool:
    """Видалити завдання остаточно"""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await conn.commit()
        return cursor.rowcount > 0

async def get_overdue_tasks(user_id: int) -> List[dict]:
    """Отримати прострочені завдання"""
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM tasks 
            WHERE user_id = ? 
              AND status = 'in_progress'
              AND (
                (due_at IS NOT NULL AND due_at < ?)
                OR (due_date IS NOT NULL AND due_date < ?)
              )
            ORDER BY priority DESC, due_at ASC, due_date ASC
            """,
            (user_id, now, today)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
