"""
Обробники команд, кнопок меню, FSM-діалогів та природної мови.
"""

import logging
from datetime import datetime, date
from html import escape

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.repositories import user_repository
from app.services import task_service
from app.services import recurrence_service
from app.repositories import recurrence_repository
from app.services.parser_service import parse_natural_language
from app.utils.keyboard import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


# =============================================================================
# СТАНИ FSM
# =============================================================================

class TaskCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_category = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()
    waiting_for_date_input = State()
    confirming = State()


# =============================================================================
# КОНСТАНТИ
# =============================================================================

PRIORITY_EMOJI = {"low": "🔵", "normal": "🟡", "high": "🔴"}
PRIORITY_LABEL = {
    "low": "🔵 Низький",
    "normal": "🟡 Звичайний",
    "high": "🔴 Високий",
}
PRIORITY_FROM_BUTTON = {
    "🔵 Низький": "low",
    "🟡 Звичайний": "normal",
    "🔴 Високий": "high",
}
CATEGORY_LABEL = {"personal": "👤 Особисте", "work": "💼 Робоче"}

# ISO номер дня тижня -> українська назва
WEEKDAY_NAMES = {
    1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Нд"
}

MENU_TEXTS = {
    "➕ Додати завдання",
    "📅 На сьогодні",
    "📆 На завтра",
    "📊 Наступні 7 днів",
    "📋 Заплановані",
    "✅ Виконані",
    "🔄 Повторювані",
    "⚙️ Налаштування",
    "❓ Допомога",
}

CANCEL_TEXT = "❌ Скасувати"
MAX_MESSAGE_LENGTH = 3500

HELP_TEXT = (
    "❓ <b>Допомога користувачу</b>\n\n"
    "Бот допомагає керувати особистими та робочими завданнями.\n\n"
    "<b>➕ Як створити завдання</b>\n"
    "1. Просто напишіть текст із датою, наприклад:\n"
    "   <code>20.10.2026 зателефонувати постачальнику</code>\n"
    "   <code>завтра о 10:00 зустріч</code>\n"
    "2. Або натисніть «➕ Додати завдання» — бот запитає все по кроках.\n\n"
    "<b>🔄 Повторювані завдання</b>\n"
    "Використовуйте слова:\n"
    "• <code>щодня</code> — кожного дня\n"
    "• <code>щотижня</code> — раз на тиждень\n"
    "• <code>щопонеділка і щоп'ятниця</code> — у вибрані дні\n"
    "• <code>кожні 3 дні</code> — з інтервалом\n"
    "• <code>щомісяця 25 числа</code> — раз на місяць\n\n"
    "<b>📋 Списки завдань</b>\n"
    "• 📅 На сьогодні — завдання на поточну дату + без строку\n"
    "• 📆 На завтра — завдання на завтра\n"
    "• 📊 Наступні 7 днів — завдання на тиждень\n"
    "• 📋 Заплановані — сьогодні + майбутнє\n"
    "• ✅ Виконані — завдання, строк яких минув\n\n"
    "<b>🗑️ Видалення</b>\n"
    "У будь-якому списку натисніть «🗑️» біля потрібного завдання.\n\n"
    "<b>⌨️ Команди</b>\n"
    "/start — головне меню\n"
    "/add — створити завдання\n"
    "/today — на сьогодні\n"
    "/tomorrow — на завтра\n"
    "/week — на 7 днів\n"
    "/planned — заплановані\n"
    "/done — виконані\n"
    "/help — допомога\n"
    "/cancel — скасувати поточну дію"
)


# =============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =============================================================================

def _escape(text: str) -> str:
    """Екранування для HTML-парсингу Telegram."""
    return escape(str(text), quote=False)


def _parse_user_date(text: str) -> str | None:
    """Парсинг дати ДД.ММ.РРРР -> РРРР-ММ-ДД."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def _normalize_date(value: str | None) -> str | None:
    """Нормалізація дати до ISO-формату."""
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

    return None


def _format_due(task: dict) -> str:
    """Людяне відображення строку завдання."""
    raw_at = task.get("due_at")
    raw_date = task.get("due_date")

    if raw_at:
        try:
            dt = datetime.fromisoformat(raw_at)
            return f"📅 {dt.strftime('%d.%m.%Y о %H:%M')}"
        except (ValueError, TypeError):
            return f"📅 {_escape(raw_at)}"

    if raw_date:
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
            return f"📅 {d.strftime('%d.%m.%Y')}"
        except (ValueError, TypeError):
            return f"📅 {_escape(raw_date)}"

    return "📅 без строку"


def _format_recurrence(rule: dict) -> str:
    """Форматування правила повторення в людський вигляд."""
    rule_type = rule.get("rule_type")
    
    if rule_type == "daily":
        return "🔁 Щодня"
    if rule_type == "every_n_days":
        n = rule.get("interval_days", 1)
        return f"🔁 Кожні {n} дн."
    if rule_type == "weekly":
        return "🔁 Щотижня"
    if rule_type == "specific_days":
        days_str = rule.get("days_of_week", "")
        try:
            days = [int(d.strip()) for d in days_str.split(",") if d.strip()]
            day_names = [WEEKDAY_NAMES.get(d, str(d)) for d in days]
            return f"🔁 По {', '.join(day_names)}"
        except (ValueError, TypeError):
            return "🔁 У вибрані дні"
    if rule_type == "monthly":
        day = rule.get("day_of_month")
        if day:
            return f"🔁 Щомісяця {day}-го"
        return "🔁 Щомісяця"
    
    return "🔁 Повторюване"


def _format_task_line(task: dict) -> str:
    """Одне завдання як HTML-рядок."""
    priority = PRIORITY_EMOJI.get(task.get("priority", "normal"), "🟡")
    category = "💼" if task.get("category") == "work" else "👤"
    status = {
        "in_progress": "⏳",
        "completed": "✅",
        "cancelled": "❌",
    }.get(task.get("status"), "⏳")

    title = _escape(task.get("title") or "Без назви")
    due = _format_due(task)
    
    # Якщо є правило повторення — додаємо позначку
    recurrence_mark = ""
    if task.get("recurrence_rule_id"):
        recurrence_mark = " 🔁"

    return f"{status} {priority} {category} <b>{title}</b>{recurrence_mark}\n   {due}"


async def _send_tasks_list(
    message: types.Message,
    title: str,
    tasks: list[dict],
) -> None:
    """Надіслати список завдань з inline-кнопками видалення."""
    if not tasks:
        await message.answer(
            f"<b>{_escape(title)}</b>\n\n📭 Завдань не знайдено.",
            parse_mode="HTML",
        )
        return

    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_size = len(title) + 20

    for task in tasks:
        line_size = len(_format_task_line(task)) + 2

        if current and current_size + line_size > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = []
            current_size = len(title) + 20

        current.append(task)
        current_size += line_size

    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) == 1:
            header = f"<b>{_escape(title)}</b> ({len(tasks)})"
        else:
            header = (
                f"<b>{_escape(title)}</b>\n"
                f"Частина {index}/{len(chunks)} · усього {len(tasks)}"
            )

        body = "\n\n".join(_format_task_line(task) for task in chunk)

        buttons = []
        for task in chunk:
            label = (task.get("title") or "Завдання").replace("\n", " ")[:24]
            buttons.append([
                types.InlineKeyboardButton(
                    text=f"🗑️ {label}",
                    callback_data=f"delete_{task['id']}",
                )
            ])

        await message.answer(
            f"{header}\n\n{body}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )


async def _show_task_list(
    message: types.Message,
    state: FSMContext,
    title: str,
    fetch_func,
) -> None:
    """Універсальне відкриття списку."""
    await state.clear()

    user_id = await user_repository.get_user_id_by_telegram_id(
        message.from_user.id
    )
    if user_id is None:
        await message.answer(
            "👋 Спочатку натисніть /start, щоб зареєструватися.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    try:
        tasks = await fetch_func(user_id)
    except Exception:
        logger.exception("Не вдалося отримати список завдань: %s", title)
        await message.answer(
            "⚠️ Не вдалося отримати список завдань. Спробуйте ще раз."
        )
        return

    await _send_tasks_list(message, title, tasks)


def _build_preview_text(data: dict) -> str:
    """Текст попереднього перегляду."""
    title = _escape(data.get("title") or "Без назви")
    category = CATEGORY_LABEL.get(data.get("category", "personal"), "👤 Особисте")
    priority = PRIORITY_LABEL.get(data.get("priority", "normal"), "🟡 Звичайний")

    due_line = "📅 дату не вказано"

    if data.get("due_at"):
        try:
            dt = datetime.fromisoformat(data["due_at"])
            due_line = f"📅 {dt.strftime('%d.%m.%Y о %H:%M')}"
        except (ValueError, TypeError):
            due_line = f"📅 {data['due_at']}"
    elif data.get("due_date"):
        norm_date = _normalize_date(data.get("due_date"))
        if norm_date:
            d = datetime.strptime(norm_date, "%Y-%m-%d").date()
            due_line = f"📅 {d.strftime('%d.%m.%Y')}"
        else:
            due_line = f"📅 {data['due_date']}"

    # Правило повторення
    recurrence_line = ""
    recurrence = data.get("recurrence")
    if recurrence:
        recurrence_line = f"\n{_format_recurrence(recurrence)}"

    return (
        f"🤖 <b>Перевірте завдання:</b>\n\n"
        f"📝 <b>{title}</b>\n"
        f"{due_line}{recurrence_line}\n"
        f"{category}\n"
        f"{priority}\n\n"
        f"Все вірно? Зберегти?"
    )


def _preview_keyboard() -> types.InlineKeyboardMarkup:
    """Кнопки попереднього перегляду."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="✅ Зберегти", callback_data="task_save"
            )],
            [
                types.InlineKeyboardButton(
                    text="📝 Категорія", callback_data="task_change_category"
                ),
                types.InlineKeyboardButton(
                    text="⭐ Пріоритет", callback_data="task_change_priority"
                ),
            ],
            [types.InlineKeyboardButton(
                text="❌ Скасувати", callback_data="task_cancel"
            )],
        ]
    )


def _empty_inline_keyboard() -> types.InlineKeyboardMarkup:
    """Порожня inline-клавіатура."""
    return types.InlineKeyboardMarkup(inline_keyboard=[])


async def _send_preview(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Надіслати нове повідомлення з попереднім переглядом."""
    data = await state.get_data()
    await message.answer(
        _build_preview_text(data),
        reply_markup=_preview_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(TaskCreation.confirming)


async def _render_preview(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    """Оновити поточне повідомлення попереднім переглядом."""
    data = await state.get_data()
    await callback.message.edit_text(
        _build_preview_text(data),
        reply_markup=_preview_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(TaskCreation.confirming)
    await callback.answer()


def _is_control_text(text: str) -> bool:
    """Чи є текст командою або кнопкою меню."""
    return (
        text.startswith("/")
        or text in MENU_TEXTS
        or text == CANCEL_TEXT
    )


# =============================================================================
# 1. КОМАНДИ ТА КНОПКИ ГОЛОВНОГО МЕНЮ
# =============================================================================

@router.message(Command("add"))
@router.message(F.text == "➕ Додати завдання")
async def cmd_add_task(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "✍️ <b>Створення завдання</b>\n\n"
        "Введіть назву завдання:",
        parse_mode="HTML",
    )
    await state.set_state(TaskCreation.waiting_for_title)


@router.message(Command("today"))
@router.message(F.text == "📅 На сьогодні")
async def show_today(message: types.Message, state: FSMContext) -> None:
    await _show_task_list(
        message, state, "📅 Завдання на сьогодні",
        task_service.get_tasks_today,
    )


@router.message(Command("tomorrow"))
@router.message(F.text == "📆 На завтра")
async def show_tomorrow(message: types.Message, state: FSMContext) -> None:
    await _show_task_list(
        message, state, "📆 Завдання на завтра",
        task_service.get_tasks_tomorrow,
    )


@router.message(Command("week"))
@router.message(F.text == "📊 Наступні 7 днів")
async def show_week(message: types.Message, state: FSMContext) -> None:
    await _show_task_list(
        message, state, "📊 Завдання на наступні 7 днів",
        task_service.get_tasks_week,
    )


@router.message(Command("planned"))
@router.message(F.text == "📋 Заплановані")
async def show_planned(message: types.Message, state: FSMContext) -> None:
    await _show_task_list(
        message, state, "📋 Заплановані завдання",
        task_service.get_planned_tasks,
    )


@router.message(Command("done"))
@router.message(F.text == "✅ Виконані")
async def show_done(message: types.Message, state: FSMContext) -> None:
    await _show_task_list(
        message, state, "✅ Виконані завдання (строк минув)",
        task_service.get_done_tasks,
    )


@router.message(Command("recurring"))
@router.message(F.text == "🔄 Повторювані")
async def show_recurring(message: types.Message, state: FSMContext) -> None:
    """Показати всі повторювані завдання користувача."""
    await state.clear()
    
    user_id = await user_repository.get_user_id_by_telegram_id(
        message.from_user.id
    )
    if user_id is None:
        await message.answer(
            "👋 Спочатку натисніть /start, щоб зареєструватися.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    try:
        rules = await recurrence_repository.get_rules_for_user(user_id)
    except Exception:
        logger.exception("Помилка отримання правил повторення")
        await message.answer(
            "⚠️ Не вдалося отримати список повторюваних завдань.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    if not rules:
        await message.answer(
            "🔄 <b>Повторювані завдання</b>\n\n"
            "📭 У вас поки немає повторюваних завдань.\n\n"
            "Щоб створити, напишіть, наприклад:\n"
            "<code>щодня перевіряти пошту</code>\n"
            "<code>щопонеділка готувати звіт</code>\n"
            "<code>кожні 3 дні передавати показники</code>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        return
    
    # Формуємо список
    body = f"<b>🔄 Повторювані завдання</b> ({len(rules)})\n\n"
    buttons = []
    
    for rule in rules:
        rule_desc = _format_recurrence(rule)
        body += f"• {rule_desc} (ID: {rule['id']})\n"
    
    body += "\n💡 Щоб видалити повторюване завдання, видаліть його зі списку завдань."
    
    await message.answer(
        body,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
@router.message(F.text == "❓ Допомога")
async def show_help(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        HELP_TEXT,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Налаштування")
async def show_settings(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚙️ Налаштування будуть доступні на Етапі 7.",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_TEXT)
async def cancel_operation(
    message: types.Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "❌ Операцію скасовано.\n\nОберіть дію:",
        reply_markup=get_main_menu_keyboard(),
    )


# =============================================================================
# 2. CALLBACK-ОБРОБНИКИ
# =============================================================================

@router.callback_query(F.data == "task_save")
async def save_task(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    logger.info("task_save від %s", callback.from_user.id)

    data = await state.get_data()

    if not data.get("title"):
        await state.clear()
        await callback.message.edit_text(
            "❌ Не вистачає назви завдання. Створіть його ще раз.",
            reply_markup=_empty_inline_keyboard(),
        )
        await callback.answer()
        return

    user_id = await user_repository.get_user_id_by_telegram_id(
        callback.from_user.id
    )
    if user_id is None:
        await callback.answer("Спочатку натисніть /start.", show_alert=True)
        return

    # Якщо є правило повторення — створюємо його в БД
    recurrence_rule_id = None
    recurrence = data.get("recurrence")
    if recurrence:
        try:
            recurrence_rule_id = await recurrence_repository.create_rule(
                rule_type=recurrence.get("rule_type"),
                interval_days=recurrence.get("interval_days"),
                days_of_week=recurrence.get("days_of_week"),
                day_of_month=recurrence.get("day_of_month"),
                execution_time=recurrence.get("execution_time"),
            )
            logger.info(f"Створено правило повторення: id={recurrence_rule_id}")
        except Exception:
            logger.exception("Помилка створення правила повторення")
            await callback.answer(
                "⚠️ Не вдалося створити правило повторення.",
                show_alert=True,
            )
            return

    try:
        result = await task_service.create_task(
            user_id=user_id,
            title=data["title"],
            category=data.get("category", "personal"),
            priority=data.get("priority", "normal"),
            due_at=data.get("due_at"),
            due_date=_normalize_date(data.get("due_date")),
            recurrence_rule_id=recurrence_rule_id,
        )
    except Exception:
        logger.exception("Помилка створення завдання")
        await callback.answer(
            "⚠️ Не вдалося зберегти завдання. Спробуйте ще раз.",
            show_alert=True,
        )
        return

    if result.get("status") != "success":
        await callback.answer(
            result.get("message", "Помилка збереження"),
            show_alert=True,
        )
        return

    # Формуємо повідомлення з урахуванням повторення
    if recurrence:
        recurrence_desc = _format_recurrence(recurrence)
        success_text = (
            f"✅ Завдання успішно створено.\n\n"
            f"{recurrence_desc}\n"
            f"Після завершення одного екземпляра бот автоматично "
            f"створить наступний."
        )
    else:
        success_text = "✅ Завдання успішно створено."

    await callback.message.edit_text(
        success_text,
        reply_markup=_empty_inline_keyboard(),
    )

    await callback.message.answer(
        "Оберіть дію:",
        reply_markup=get_main_menu_keyboard(),
    )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "task_change_category")
async def change_category(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    if not data.get("title"):
        await callback.answer("Немає активного завдання.", show_alert=True)
        return

    await callback.message.edit_text(
        "📝 <b>Оберіть категорію:</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="👤 Особисте", callback_data="set_personal"
                )],
                [types.InlineKeyboardButton(
                    text="💼 Робоче", callback_data="set_work"
                )],
                [types.InlineKeyboardButton(
                    text="↩️ Назад", callback_data="back_to_preview"
                )],
            ]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "set_personal")
async def set_personal(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(category="personal")
    await _render_preview(callback, state)


@router.callback_query(F.data == "set_work")
async def set_work(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(category="work")
    await _render_preview(callback, state)


@router.callback_query(F.data == "task_change_priority")
async def change_priority(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    if not data.get("title"):
        await callback.answer("Немає активного завдання.", show_alert=True)
        return

    await callback.message.edit_text(
        "⭐ <b>Оберіть пріоритет:</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="🔵 Низький", callback_data="set_low"
                )],
                [types.InlineKeyboardButton(
                    text="🟡 Звичайний", callback_data="set_normal"
                )],
                [types.InlineKeyboardButton(
                    text="🔴 Високий", callback_data="set_high"
                )],
                [types.InlineKeyboardButton(
                    text="↩️ Назад", callback_data="back_to_preview"
                )],
            ]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "set_low")
async def set_low(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(priority="low")
    await _render_preview(callback, state)


@router.callback_query(F.data == "set_normal")
async def set_normal(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(priority="normal")
    await _render_preview(callback, state)


@router.callback_query(F.data == "set_high")
async def set_high(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(priority="high")
    await _render_preview(callback, state)


@router.callback_query(F.data == "back_to_preview")
async def back_to_preview(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await _render_preview(callback, state)


@router.callback_query(F.data == "task_cancel")
async def cancel_task_creation(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.message.edit_text(
        "❌ Створення завдання скасовано.",
        reply_markup=_empty_inline_keyboard(),
    )
    await callback.message.answer(
        "Оберіть дію:",
        reply_markup=get_main_menu_keyboard(),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("delete_confirm_"))
async def confirm_delete(callback: types.CallbackQuery) -> None:
    try:
        task_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer()
        return

    user_id = await user_repository.get_user_id_by_telegram_id(
        callback.from_user.id
    )
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    try:
        result = await task_service.delete_task(task_id, user_id)
    except Exception:
        logger.exception("Помилка видалення завдання %s", task_id)
        await callback.answer(
            "⚠️ Не вдалося видалити завдання. Спробуйте ще раз.",
            show_alert=True,
        )
        return

    if result.get("status") == "success":
        await callback.message.edit_text(
            "✅ Завдання видалено.",
            reply_markup=_empty_inline_keyboard(),
        )
        await callback.answer("Завдання видалено.")
    else:
        await callback.message.edit_text(
            "ℹ️ Завдання вже видалено або недоступне.",
            reply_markup=_empty_inline_keyboard(),
        )
        await callback.answer()


@router.callback_query(F.data.startswith("delete_cancel_"))
async def cancel_delete(callback: types.CallbackQuery) -> None:
    await callback.message.edit_text(
        "↩️ Видалення скасовано. Завдання залишилося.",
        reply_markup=_empty_inline_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_"))
async def ask_delete(callback: types.CallbackQuery) -> None:
    raw = callback.data or ""
    parts = raw.split("_")

    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer()
        return

    task_id = int(parts[1])

    user_id = await user_repository.get_user_id_by_telegram_id(
        callback.from_user.id
    )
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    try:
        task = await task_service.get_task(task_id, user_id)
    except Exception:
        logger.exception("Помилка отримання завдання %s", task_id)
        await callback.answer(
            "⚠️ Не вдалося отримати завдання.", show_alert=True
        )
        return

    if task is None:
        await callback.answer(
            "Завдання вже видалено. Оновіть список.", show_alert=True
        )
        return

    title = _escape(task.get("title") or "Без назви")

    await callback.message.answer(
        f"🗑️ <b>Видалити завдання?</b>\n\n"
        f"📝 {title}\n\n"
        f"Цю дію неможливо скасувати.",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="✅ Так, видалити",
                    callback_data=f"delete_confirm_{task_id}",
                )],
                [types.InlineKeyboardButton(
                    text="↩️ Ні, залишити",
                    callback_data=f"delete_cancel_{task_id}",
                )],
            ]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query()
async def unknown_callback(callback: types.CallbackQuery) -> None:
    logger.debug("Невідомий callback: %s", callback.data)
    await callback.answer()


# =============================================================================
# 3. FSM: ПОКРОКОВЕ СТВОРЕННЯ
# =============================================================================

@router.message(TaskCreation.waiting_for_title)
async def process_title(
    message: types.Message,
    state: FSMContext,
) -> None:
    text = (message.text or "").strip()

    if not text or _is_control_text(text):
        await message.answer(
            "Введіть назву завдання звичайним текстом."
        )
        return

    await state.update_data(title=text)

    await message.answer(
        "Оберіть категорію:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="👤 Особисте"),
                    types.KeyboardButton(text="💼 Робоче"),
                ],
                [types.KeyboardButton(text=CANCEL_TEXT)],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(TaskCreation.waiting_for_category)


@router.message(
    TaskCreation.waiting_for_category,
    F.text.in_(["👤 Особисте", "💼 Робоче"]),
)
async def process_category(
    message: types.Message,
    state: FSMContext,
) -> None:
    category = "personal" if "Особисте" in message.text else "work"
    await state.update_data(category=category)

    await message.answer(
        "Оберіть пріоритет:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="🔵 Низький"),
                    types.KeyboardButton(text="🟡 Звичайний"),
                    types.KeyboardButton(text="🔴 Високий"),
                ],
                [types.KeyboardButton(text=CANCEL_TEXT)],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(TaskCreation.waiting_for_priority)


@router.message(
    TaskCreation.waiting_for_priority,
    F.text.in_(list(PRIORITY_FROM_BUTTON.keys())),
)
async def process_priority(
    message: types.Message,
    state: FSMContext,
) -> None:
    priority = PRIORITY_FROM_BUTTON.get(message.text, "normal")
    await state.update_data(priority=priority)

    await message.answer(
        "📅 Введіть дату виконання у форматі <b>ДД.ММ.РРРР</b>\n"
        "Наприклад: <code>20.10.2026</code>",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await state.set_state(TaskCreation.waiting_for_due_date)


@router.message(TaskCreation.waiting_for_due_date)
@router.message(TaskCreation.waiting_for_date_input)
async def process_any_date(
    message: types.Message,
    state: FSMContext,
) -> None:
    due_date = _parse_user_date(message.text or "")

    if not due_date:
        await message.answer(
            "❌ Невірний формат дати.\n\n"
            "Введіть дату як <b>ДД.ММ.РРРР</b>, "
            "наприклад <code>20.10.2026</code>.",
            parse_mode="HTML",
        )
        return

    await state.update_data(due_date=due_date)
    await _send_preview(message, state)


@router.message(TaskCreation.confirming)
async def confirming_guard(
    message: types.Message,
    state: FSMContext,
) -> None:
    await message.answer(
        "📎 Підтвердіть або скасуйте створення кнопками "
        "під повідомленням з попереднім переглядом."
    )


# =============================================================================
# 4. ПРИРОДНА МОВА — САМЕ ОСТАННІЙ
# =============================================================================

@router.message(F.text, StateFilter(None))
async def handle_natural_language_task(
    message: types.Message,
    state: FSMContext,
) -> None:
    text = (message.text or "").strip()

    if not text or _is_control_text(text):
        return

    logger.info("Природна мова від %s: '%s'", message.from_user.id, text)

    try:
        parsed = parse_natural_language(text)
    except Exception:
        logger.exception("Помилка парсера природної мови")
        await message.answer(
            "⚠️ Не вдалося розпізнати завдання. "
            "Спробуйте написати простіше, наприклад:\n"
            "<code>20.10.2026 купити молоко</code>",
            parse_mode="HTML",
        )
        return

    title = (parsed.get("title") or "").strip()

    if not title or title == "Нове завдання":
        await message.answer(
            "🤔 Я не розпізнав назву завдання.\n\n"
            "Напишіть, наприклад:\n"
            "<code>20.10.2026 купити молоко</code>\n"
            "або натисніть «➕ Додати завдання».",
            parse_mode="HTML",
        )
        return

    await state.update_data(
        title=title,
        category=parsed.get("category", "personal"),
        priority=parsed.get("priority", "normal"),
    )

    due_date = _normalize_date(parsed.get("due_date"))
    due_at = parsed.get("due_at")
    recurrence = parsed.get("recurrence")

    # Якщо є повторення — зберігаємо його
    if recurrence:
        await state.update_data(recurrence=recurrence)

    # Якщо немає дати, але є повторення — використовуємо сьогодні як базу
    if not due_date and not due_at:
        if recurrence:
            due_date = date.today().isoformat()
            logger.info(
                f"Для повторюваного завдання встановлено базову дату: {due_date}"
            )
            await state.update_data(due_date=due_date)
            await _send_preview(message, state)
            return
        else:
            # Звичайне завдання без дати — просимо ввести
            await message.answer(
                "📅 Вкажіть дату виконання у форматі <b>ДД.ММ.РРРР</b>\n"
                "Наприклад: <code>20.10.2026</code>",
                parse_mode="HTML",
            )
            await state.set_state(TaskCreation.waiting_for_date_input)
            return

    # Зберігаємо дату/час
    if due_date:
        await state.update_data(due_date=due_date)
    if due_at:
        await state.update_data(due_at=due_at)

    await _send_preview(message, state)
