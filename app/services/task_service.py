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
    due_date: Optional[str] = None
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
        due_date=due_date
    )
    
    logger.info(f"Завдання створено: task_id={task_id}")
    return {"status": "success", "task_id": task_id, "message": "Завдання успішно створено"}

async def get_task(task_id: int, user_id: int) -> Optional[dict]:
    """Отримати завдання"""
    return await task_repository.get_task(task_id, user_id)

async def get_tasks_today(user_id: int) -> List[dict]:
    """Отримати завдання на сьогодні"""
    today = date.today().isoformat()
    now = datetime.utcnow().isoformat()
    
    tasks = await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="in_progress",
        due_date_from=today,
        due_date_to=today,
        due_at_from=now,
        due_at_to=f"{today}T23:59:59"
    )
    
    no_due_tasks = await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="in_progress",
        has_due_date=False
    )
    
    return tasks + no_due_tasks

async def get_tasks_tomorrow(user_id: int) -> List[dict]:
    """Отримати завдання на завтра"""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    return await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="in_progress",
        due_date_from=tomorrow,
        due_date_to=tomorrow
    )

async def get_tasks_week(user_id: int) -> List[dict]:
    """Отримати завдання на наступні 7 днів"""
    today = date.today().isoformat()
    week_later = (date.today() + timedelta(days=7)).isoformat()
    
    return await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="in_progress",
        due_date_from=today,
        due_date_to=week_later
    )

async def get_overdue_tasks(user_id: int) -> List[dict]:
    """Отримати прострочені завдання"""
    return await task_repository.get_overdue_tasks(user_id)

async def get_active_tasks(user_id: int) -> List[dict]:
    """Отримати всі активні завдання"""
    return await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="in_progress"
    )

async def get_tasks_without_due_date(user_id: int) -> List[dict]:
    """Отримати завдання без строку"""
    return await task_repository.get_tasks_without_due_date(user_id)

async def get_completed_tasks(user_id: int, limit: int = 50) -> List[dict]:
    """Отримати виконані завдання"""
    return await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="completed",
        limit=limit
    )

async def get_cancelled_tasks(user_id: int, limit: int = 50) -> List[dict]:
    """Отримати скасовані завдання"""
    return await task_repository.get_tasks_by_filter(
        user_id=user_id,
        status="cancelled",
        limit=limit
    )

async def complete_task(task_id: int, user_id: int) -> dict:
    """Позначити завдання як виконане"""
    task = await task_repository.get_task(task_id, user_id)
    if not task:
        return {"status": "error", "message": "Завдання не знайдено"}
    
    if task['status'] == 'completed':
        return {"status": "error", "message": "Завдання вже виконане"}
    
    success = await task_repository.update_task(
        task_id, user_id,
        status="completed",
        completed_at=datetime.utcnow().isoformat()
    )
    
    if success:
        return {"status": "success", "message": "Завдання позначено як виконане"}
    return {"status": "error", "message": "Помилка оновлення завдання"}

async def cancel_task(task_id: int, user_id: int) -> dict:
    """Скасувати завдання"""
    task = await task_repository.get_task(task_id, user_id)
    if not task:
        return {"status": "error", "message": "Завдання не знайдено"}
    
    if task['status'] == 'cancelled':
        return {"status": "error", "message": "Завдання вже скасоване"}
    
    success = await task_repository.update_task(
        task_id, user_id,
        status="cancelled"
    )
    
    if success:
        return {"status": "success", "message": "Завдання скасовано"}
    return {"status": "error", "message": "Помилка оновлення завдання"}

async def restore_task(task_id: int, user_id: int) -> dict:
    """Відновити скасоване або виконане завдання"""
    task = await task_repository.get_task(task_id, user_id)
    if not task:
        return {"status": "error", "message": "Завдання не знайдено"}
    
    if task['status'] == 'in_progress':
        return {"status": "error", "message": "Завдання вже активне"}
    
    success = await task_repository.update_task(
        task_id, user_id,
        status="in_progress",
        completed_at=None
    )
    
    if success:
        return {"status": "success", "message": "Завдання відновлено"}
    return {"status": "error", "message": "Помилка оновлення завдання"}

async def delete_task(task_id: int, user_id: int) -> dict:
    """Видалити завдання остаточно"""
    success = await task_repository.delete_task(task_id, user_id)
    
    if success:
        return {"status": "success", "message": "Завдання видалено"}
    return {"status": "error", "message": "Завдання не знайдено або вже видалено"}
