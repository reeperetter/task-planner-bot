"""Сервіс для роботи з повторюваними завданнями."""

import logging
import calendar
from datetime import datetime, date, timedelta
from typing import Optional
from app.repositories import recurrence_repository, task_repository

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    "пн": 1, "пон": 1, "понед": 1, "понеділок": 1,
    "вт": 2, "вів": 2, "вівтор": 2, "вівторок": 2,
    "ср": 3, "сер": 3, "серед": 3, "середа": 3,
    "чт": 4, "чет": 4, "четвер": 4,
    "пт": 5, "пят": 5, "п'ят": 5, "пятниц": 5, "п'ятниц": 5,
    "сб": 6, "суб": 6, "субот": 6, "субота": 6,
    "нд": 7, "нед": 7, "неділ": 7, "неділя": 7,
}


def parse_days_of_week(text: str) -> list[int]:
    """Парсить рядок із днями тижня у список ISO-номерів."""
    result = set()
    text_lower = text.lower()

    for key, value in WEEKDAY_MAP.items():
        if key in text_lower:
            result.add(value)

    if not result:
        for part in text_lower.replace(",", " ").replace(";", " ").split():
            part = part.strip()
            if part.isdigit():
                num = int(part)
                if 1 <= num <= 7:
                    result.add(num)

    return sorted(result)


def calculate_next_date(
    rule: dict,
    current_due_date: date,
    execution_time: Optional[str] = None,
) -> Optional[date]:
    """Обчислює наступну дату виконання за правилом повторення."""
    rule_type = rule.get("rule_type")

    if rule_type == "daily":
        return current_due_date + timedelta(days=1)

    if rule_type == "every_n_days":
        interval = rule.get("interval_days")
        if not interval or interval <= 0:
            return None
        return current_due_date + timedelta(days=interval)

    if rule_type == "weekly":
        return current_due_date + timedelta(weeks=1)

    if rule_type == "specific_days":
        days_str = rule.get("days_of_week")
        if not days_str:
            return None

        try:
            allowed_days = [int(d.strip()) for d in days_str.split(",") if d.strip()]
        except ValueError:
            return None

        if not allowed_days:
            return None

        for i in range(1, 8):
            candidate = current_due_date + timedelta(days=i)
            if candidate.isoweekday() in allowed_days:
                return candidate
        return None

    if rule_type == "monthly":
        day_of_month = rule.get("day_of_month")
        if not day_of_month:
            day_of_month = current_due_date.day

        year = current_due_date.year
        month = current_due_date.month + 1
        if month > 12:
            month = 1
            year += 1

        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)

        return date(year, month, actual_day)

    if rule_type == "every_n_months":
        interval = rule.get("interval_months")
        if not interval or interval <= 0:
            return None
        
        day_of_month = current_due_date.day
        
        year = current_due_date.year
        month = current_due_date.month + interval
        
        # Обробка переходу через рік
        while month > 12:
            month -= 12
            year += 1
        
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)
        
        return date(year, month, actual_day)

    if rule_type == "yearly":
        interval = rule.get("interval_years")
        if not interval or interval <= 0:
            return None
        
        year = current_due_date.year + interval
        month = current_due_date.month
        day_of_month = current_due_date.day
        
        # Обробка 29 лютого у невисокосний рік
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)
        
        return date(year, month, actual_day)

    logger.warning(f"Невідомий тип правила: {rule_type}")
    return None


def calculate_next_date_after_today(rule: dict) -> Optional[date]:
    """
    Обчислює найближчу дату виконання після сьогодні для повторюваного завдання.
    Використовується, коли початкова дата в минулому.
    """
    today = date.today()
    rule_type = rule.get("rule_type")

    if rule_type == "daily":
        return today + timedelta(days=1)

    if rule_type == "every_n_days":
        interval = rule.get("interval_days")
        if not interval or interval <= 0:
            return None
        # Знаходимо найближчу дату після сьогодні
        candidate = today + timedelta(days=1)
        return candidate

    if rule_type == "weekly":
        return today + timedelta(weeks=1)

    if rule_type == "specific_days":
        days_str = rule.get("days_of_week")
        if not days_str:
            return None

        try:
            allowed_days = [int(d.strip()) for d in days_str.split(",") if d.strip()]
        except ValueError:
            return None

        if not allowed_days:
            return None

        # Шукаємо найближчий дозволений день після сьогодні
        for i in range(1, 8):
            candidate = today + timedelta(days=i)
            if candidate.isoweekday() in allowed_days:
                return candidate
        return None

    if rule_type == "monthly":
        day_of_month = rule.get("day_of_month")
        if not day_of_month:
            day_of_month = today.day

        year = today.year
        month = today.month + 1
        if month > 12:
            month = 1
            year += 1

        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)

        return date(year, month, actual_day)

    if rule_type == "every_n_months":
        interval = rule.get("interval_months")
        if not interval or interval <= 0:
            return None
        
        day_of_month = today.day
        
        year = today.year
        month = today.month + interval
        
        while month > 12:
            month -= 12
            year += 1
        
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)
        
        return date(year, month, actual_day)

    if rule_type == "yearly":
        interval = rule.get("interval_years")
        if not interval or interval <= 0:
            return None
        
        year = today.year + interval
        month = today.month
        day_of_month = today.day
        
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(day_of_month, max_day)
        
        return date(year, month, actual_day)

    logger.warning(f"Невідомий тип правила: {rule_type}")
    return None


async def create_next_instance(task_id: int, user_id: int) -> Optional[int]:
    """Створює наступний екземпляр повторюваного завдання."""
    task = await task_repository.get_task(task_id, user_id)
    if not task:
        logger.warning(f"Завдання {task_id} не знайдено")
        return None

    rule_id = task.get("recurrence_rule_id")
    if not rule_id:
        logger.info(f"Завдання {task_id} не є повторюваним")
        return None

    rule = await recurrence_repository.get_rule(rule_id)
    if not rule:
        logger.warning(f"Правило {rule_id} не знайдено")
        return None

    current_date: Optional[date] = None
    if task.get("due_date"):
        try:
            current_date = date.fromisoformat(task["due_date"])
        except ValueError:
            pass
    elif task.get("due_at"):
        try:
            current_date = datetime.fromisoformat(task["due_at"]).date()
        except ValueError:
            pass

    if not current_date:
        logger.warning(f"Завдання {task_id} не має дати для обчислення наступної")
        return None

    next_date = calculate_next_date(
        rule, current_date, rule.get("execution_time")
    )

    if not next_date:
        logger.warning(f"Не вдалося обчислити наступну дату для завдання {task_id}")
        return None

    # Перевірка на дублікати
    existing = await task_repository.get_tasks_for_date(user_id, next_date)
    for t in existing:
        if (
            t.get("title") == task.get("title")
            and t.get("recurrence_rule_id") == rule_id
        ):
            logger.info(
                f"Наступний екземпляр вже існує: task_id={t['id']}, date={next_date}"
            )
            return t["id"]

    # Створення нового екземпляра
    execution_time = rule.get("execution_time")
    due_at = None
    due_date_str = next_date.isoformat()

    if execution_time:
        try:
            due_datetime = datetime.combine(next_date, datetime.strptime(execution_time, "%H:%M").time())
            due_at = due_datetime.isoformat()
            due_date_str = None
        except ValueError:
            pass

    new_task_id = await task_repository.create_task(
        user_id=user_id,
        title=task["title"],
        category=task.get("category", "personal"),
        priority=task.get("priority", "normal"),
        due_at=due_at,
        due_date=due_date_str,
        recurrence_rule_id=rule_id,
    )

    logger.info(
        f"Створено наступний екземпляр: task_id={new_task_id}, "
        f"date={next_date}, rule_id={rule_id}"
    )
    return new_task_id
