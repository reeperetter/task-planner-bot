from datetime import datetime, date
from typing import Optional

def format_task_for_display(task: dict) -> str:
    """Форматувати завдання для відображення"""
    status_emoji = {
        'in_progress': '⏳',
        'completed': '✅',
        'cancelled': '❌'
    }
    
    priority_emoji = {
        'low': '🔵',
        'normal': '🟡',
        'high': '🔴'
    }
    
    category_emoji = {
        'personal': '👤',
        'work': '💼'
    }
    
    status = status_emoji.get(task['status'], '⏳')
    priority = priority_emoji.get(task['priority'], '🟡')
    category = category_emoji.get(task['category'], '👤')
    
    # Форматування дати
    due_info = ""
    if task.get('due_at'):
        try:
            dt = datetime.fromisoformat(task['due_at'])
            due_info = f"📅 {dt.strftime('%d.%m.%Y %H:%M')}"
        except:
            due_info = f"📅 {task['due_at']}"
    elif task.get('due_date'):
        try:
            d = date.fromisoformat(task['due_date'])
            due_info = f"📅 {d.strftime('%d.%m.%Y')}"
        except:
            due_info = f"📅 {task['due_date']}"
    else:
        due_info = "📅 без строку"
    
    return (
        f"{status} {priority} {category} <b>{task['title']}</b>\n"
        f"   {due_info} | ID: {task['id']}"
    )

def format_tasks_list(tasks: list, title: str) -> str:
    """Форматувати список завдань"""
    if not tasks:
        return f"{title}\n\n📭 Завдань не знайдено"
    
    result = f"<b>{title}</b> ({len(tasks)})\n\n"
    for task in tasks:
        result += format_task_for_display(task) + "\n\n"
    
    return result.strip()
