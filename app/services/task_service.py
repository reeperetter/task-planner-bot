import logging
from typing import Optional, List, Dict, Any
from datetime import timedelta
from app.repositories import task_repository, recurrence_repository
from app.services import recurrence_service
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
) -> dict:
    """Створити нове завдання."""
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
    """Отримати завдання."""
    return await task_repository.get_task(task_id, user_id)


async def get_tasks_today(user_id: int) -> List[dict]:
    """Отримати завдання на сьогодні (з датою сьогодні + без строку)."""
    today = today_kyiv()
    tasks_with_date = await task_repository.get_tasks_for_date(user_id, today)
    tasks_no_date = await task_repository.get_tasks_without_due_date(user_id)
    return tasks_with_date + tasks_no_date


async def get_tasks_tomorrow(user_id: int) -> List[dict]:
    """Отримати завдання на завтра."""
    tomorrow = today_kyiv() + timedelta(days=1)
    return await task_repository.get_tasks_for_date(user_id, tomorrow)


async def get_tasks_week(user_id: int) -> List[dict]:
    """Отримати завдання на наступні 7 днів (включаючи сьогодні)."""
    today = today_kyiv()
    week_later = today + timedelta(days=6)
    return await task_repository.get_tasks_for_date_range(user_id, today, week_later)


async def get_planned_tasks(user_id: int) -> List[dict]:
    """Отримати заплановані завдання (сьогодні + майбутнє)."""
    return await task_repository.get_planned_tasks(user_id)


async def get_done_tasks(user_id: int) -> List[dict]:
    """Отримати виконані завдання (status = 'completed')."""
    return await task_repository.get_done_tasks(user_id)


async def get_recurring_tasks(user_id: int) -> List[dict]:
    """Отримати всі активні повторювані завдання користувача."""
    return await task_repository.get_recurring_tasks(user_id)


async def get_tasks_without_due_date(user_id: int) -> List[dict]:
    """Отримати завдання без строку."""
    return await task_repository.get_tasks_without_due_date(user_id)


async def complete_task(task_id: int, user_id: int) -> dict:
    """
    Позначити завдання як виконане.
    Якщо завдання повторюване — створює наступний екземпляр.
    """
    task = await task_repository.get_task(task_id, user_id)
    if not task:
        return {"status": "error", "message": "Завдання не знайдено"}

    if task["status"] == "completed":
        return {"status": "error", "message": "Завдання вже виконане"}

    success = await task_repository.update_task(
        task_id,
        user_id,
        status="completed",
        completed_at=to_kyiv_naive(),
    )

    if not success:
        return {"status": "error", "message": "Помилка оновлення завдання"}

    new_task_id = None
    if task.get("recurrence_rule_id"):
        new_task_id = await recurrence_service.create_next_instance(task_id, user_id)
        if new_task_id:
            logger.info(f"Створено наступний екземпляр: task_id={new_task_id}")

    return {
        "status": "success",
        "message": "Завдання виконано",
        "new_task_id": new_task_id,
    }


async def delete_task(task_id: int, user_id: int) -> dict:
    """
    Видалити завдання остаточно.
    Якщо завдання було повторюваним і це був останній активний екземпляр —
    автоматично видаляє правило повторення.
    """
    task = await task_repository.get_task(task_id, user_id)
    rule_id = task.get("recurrence_rule_id") if task else None

    success = await task_repository.delete_task(task_id, user_id)

    if not success:
        return {"status": "error", "message": "Завдання не знайдено або вже видалено"}

    if rule_id:
        remaining = await task_repository.count_active_tasks_by_rule(rule_id)
        if remaining == 0:
            try:
                await recurrence_repository.delete_rule(rule_id)
                logger.info(f"Видалено правило-сироту: rule_id={rule_id}")
            except Exception:
                logger.exception(f"Не вдалося видалити правило-сироту {rule_id}")

    return {"status": "success", "message": "Завдання видалено"}


async def search_tasks(user_id: int, query: str) -> List[Dict[str, Any]]:
    return await task_repository.search_tasks(user_id, query)


async def get_filtered_tasks(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    return await task_repository.get_filtered_tasks(user_id, category, priority)


async def get_tasks_today_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    today = today_kyiv()
    return await task_repository.get_tasks_for_date_filtered(user_id, today, category, priority)


async def get_tasks_tomorrow_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    tomorrow = today_kyiv() + timedelta(days=1)
    return await task_repository.get_tasks_for_date_filtered(user_id, tomorrow, category, priority)


async def get_tasks_week_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    today = today_kyiv()
    week_end = today + timedelta(days=6)
    return await task_repository.get_tasks_for_date_range_filtered(user_id, today, week_end, category, priority)


async def get_planned_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    return await task_repository.get_planned_tasks_filtered(user_id, category, priority)


async def get_done_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    return await task_repository.get_done_tasks_filtered(user_id, category, priority)


async def get_recurring_tasks_filtered(user_id: int, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
    return await task_repository.get_recurring_tasks_filtered(user_id, category, priority)
