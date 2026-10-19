import logging
from typing import Optional, List
from datetime import datetime, date, timedelta
from app.repositories import task_repository

logger = logging.getLogger(__name__)

async def create_task(
    user_id: int,
    title: str,
    category: str = "personal",
    priority: str = "normal",
    due_at: Optional[str] = None,
    due_date: Optional[str] = None,
    recurrence_rule_id: Optional[int] = None,
) -> dict:
    """Створити нове завдання"""
    if not title or not title.strip():
        return {"status": "error", "message": "Назва завдання не може бути порожньою"}
    
    task_id = await task_repository.create_task(
        user_id=user_id,
        title=title.strip(),
        category=category,
        priority=priority,
        due_at=due_at,
        due_date=due_date,
        recurrence_rule_id=recurrence_rule_id,
    )
    
    logger.info(f"Завдання створено: task_id={task_id}")
    return {"status": "success", "task_id": task_id, "message": "Завдання успішно створено"}

async def get_task(task_id: int, user_id: int) -> Optional[dict]:
    """Отримати завдання"""
    return await task_repository.get_task(task_id, user_id)

async def get_tasks_today(user_id: int) -> List[dict]:
    """Отримати завдання на сьогодні (з датою сьогодні + без строку)"""
    today = date.today()
    tasks_with_date = await task_repository.get_tasks_for_date(user_id, today)
    tasks_no_date = await task_repository.get_tasks_without_due_date(user_id)
    return tasks_with_date + tasks_no_date

async def get_tasks_tomorrow(user_id: int) -> List[dict]:
    """Отримати завдання на завтра"""
    tomorrow = date.today() + timedelta(days=1)
    return await task_repository.get_tasks_for_date(user_id, tomorrow)

async def get_tasks_week(user_id: int) -> List[dict]:
    """Отримати завдання на наступні 7 днів (включаючи сьогодні)"""
    today = date.today()
    week_later = today + timedelta(days=7)
    return await task_repository.get_tasks_for_date_range(user_id, today, week_later)

async def get_planned_tasks(user_id: int) -> List[dict]:
    """Отримати заплановані завдання (сьогодні + майбутнє)"""
    return await task_repository.get_planned_tasks(user_id)

async def get_done_tasks(user_id: int) -> List[dict]:
    """Отримати виконані завдання (строк минув)"""
    return await task_repository.get_done_tasks(user_id)

async def get_tasks_without_due_date(user_id: int) -> List[dict]:
    """Отримати завдання без строку"""
    return await task_repository.get_tasks_without_due_date(user_id)

async def delete_task(task_id: int, user_id: int) -> dict:
    """Видалити завдання остаточно"""
    success = await task_repository.delete_task(task_id, user_id)
    
    if success:
        return {"status": "success", "message": "Завдання видалено"}
    return {"status": "error", "message": "Завдання не знайдено або вже видалено"}
