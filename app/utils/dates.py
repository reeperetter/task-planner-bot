from datetime import datetime, date
from aiogram import types

def format_task_line(task: dict) -> str:
    """Форматувати одне завдання як рядок тексту"""
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
    
    return f"{status} {priority} {category} <b>{task['title']}</b>\n   {due_info}"

def format_tasks_list(tasks: list, title: str) -> tuple[str, types.InlineKeyboardMarkup | None]:
    """
    Форматувати список завдань з inline-кнопками видалення під кожним завданням.
    Повертає (текст, клавіатура).
    """
    if not tasks:
        return f"<b>{title}</b>\n\n📭 Завдань не знайдено", None
    
    result = f"<b>{title}</b> ({len(tasks)})\n\n"
    buttons = []
    
    for task in tasks:
        result += format_task_line(task) + "\n\n"
        # Кнопка видалення для кожного завдання
        buttons.append([
            types.InlineKeyboardButton(
                text=f"🗑️ Видалити: {task['title'][:20]}",
                callback_data=f"delete_{task['id']}"
            )
        ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    return result.strip(), keyboard
