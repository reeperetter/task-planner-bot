from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from html import escape
from aiogram import types

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def now_kyiv() -> datetime:
    """Поточний час у часовому поясі Europe/Kyiv (timezone-aware)."""
    return datetime.now(KYIV_TZ)


def today_kyiv() -> date:
    """Поточна дата у часовому поясі Europe/Kyiv."""
    return now_kyiv().date()


def to_kyiv_naive(dt: datetime | None = None) -> datetime:
    """Повертає наївний datetime у часовому поясі Europe/Kyiv (для зберігання в TIMESTAMP без TZ)."""
    if dt is None:
        return now_kyiv().replace(tzinfo=None)
    if dt.tzinfo is not None:
        return dt.astimezone(KYIV_TZ).replace(tzinfo=None)
    return dt


def format_due(task: dict) -> str:
    """Форматувати строк виконання завдання."""
    raw_at = task.get("due_at")
    raw_date = task.get("due_date")

    if raw_at:
        try:
            dt = datetime.fromisoformat(raw_at) if isinstance(raw_at, str) else raw_at
            if dt.tzinfo is not None:
                dt = dt.astimezone(KYIV_TZ)
            return dt.strftime("%d.%m.%Y о %H:%M")
        except (ValueError, TypeError, AttributeError):
            return str(raw_at)

    if raw_date:
        try:
            d = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
            return d.strftime("%d.%m.%Y")
        except (ValueError, TypeError, AttributeError):
            return str(raw_date)

    return "без строку"


def format_task_line(task: dict, index: int = 0) -> str:
    """Форматувати одне завдання як рядок HTML-тексту."""
    priority_emoji = {"low": "🔵", "normal": "🟡", "high": "🔴"}
    priority = priority_emoji.get(task.get("priority", "normal"), "🟡")
    category = "💼" if task.get("category") == "work" else "👤"
    title = escape(str(task.get("title") or "Без назви"), quote=False)
    due = format_due(task)
    recurrence_mark = " 🔁" if task.get("recurrence_rule_id") else ""
    date_and_meta = f"{due} {priority} {category}{recurrence_mark}"

    if index > 0:
        return f"{index}. <b>{title}</b>\n   {date_and_meta}"
    return f"<b>{title}</b>\n   {date_and_meta}"


def format_tasks_list(tasks: list, title: str) -> tuple[str, types.InlineKeyboardMarkup | None]:
    """Форматувати список завдань з inline-кнопками видалення під кожним завданням."""
    if not tasks:
        return f"<b>{escape(title, quote=False)}</b>\n\n📭 Завдань не знайдено", None

    result = f"<b>{escape(title, quote=False)}</b> ({len(tasks)})\n\n"
    buttons = []

    for idx, task in enumerate(tasks, start=1):
        result += format_task_line(task, idx) + "\n\n"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"🗑️ Видалити: {str(task['title'])[:20]}",
                callback_data=f"delete_{task['id']}"
            )
        ])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    return result.strip(), keyboard
