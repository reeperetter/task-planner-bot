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
    waiting_for_date_change = State()
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

WEEKDAY_NAMES = {
    1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Нд"
}

MENU_TEXTS = {
    "➕ Додати завдання",
    "🔍 Пошук",
    "📅 На сьогодні",
    "📆 На завтра",
    "📊 Наступні 7 днів",
    "📋 Заплановані",
    "✅ Виконані",
    "🔄 Повторювані",
    "❓ Допомога",
}

CANCEL_TEXT = "❌ Скасувати"
MAX_MESSAGE_LENGTH = 3500

HELP_TEXT = (
    "❓ <b>Допомога користувачу</b>\n\n"
    "Я — ваш особистий планувальник. Допоможу не забувати про важливі справи.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>➕ ЯК СТВОРИТИ ЗАВДАННЯ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>Спосіб 1: Природна мова (найшвидший)</b>\n"
    "Просто напишіть текст. Я сам розпізнаю деталі:\n"
    "• <code>купити молоко</code> (я попрошу вказати дату)\n"
    "• <code>20.10.2026 зателефонувати постачальнику</code>\n"
    "• <code>завтра підготувати звіт</code>\n"
    "• <code>післязавтра о 18:30 зустріч</code>\n"
    "• <code>щодня перевіряти пошту</code>\n"
    "• <code>щопонеділка і щоп'ятниця тренування</code>\n"
    "• <code>кожні 3 дні передавати показники</code>\n"
    "• <code>кожні 2 тижні зустрічатися з командою</code>\n"
    "• <code>кожні 2 місяці платити за оренду</code>\n"
    "• <code>щомісяця 25 числа оплачувати рахунки</code>\n\n"
    "Після введення я покажу попередній перегляд, де ви зможете змінити категорію, пріоритет або дату кнопками.\n\n"
    "<b>Спосіб 2: Покрокове створення</b>\n"
    "Натисніть «➕ Додати завдання», і я запитаю назву, категорію, пріоритет і дату по черзі.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>🔄 ПОВТОРЮВАНІ ЗАВДАННЯ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Використовуйте слова-маркери:\n"
    "• <code>щодня</code> / <code>щоденно</code> — кожного дня\n"
    "• <code>щотижня</code> — раз на тиждень (того ж дня)\n"
    "• <code>щопонеділка</code>, <code>щовівторка</code>... — у конкретний день\n"
    "• <code>щопонеділка і щоп'ятниця</code> — у кілька днів\n"
    "• <code>кожні N днів/тижнів/місяців/років</code> — з інтервалом\n"
    "• <code>щомісяця N числа</code> — конкретне число місяця\n\n"
    "Повторювані завдання позначаються значком 🔁 у кінці рядка з датою. Щоб зупинити повторення, просто видаліть завдання.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>📋 СПИСКИ ЗАВДАНЬ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• <b>📅 На сьогодні</b> — завдання на поточну дату + без строку\n"
    "• <b>📆 На завтра</b> — завдання на завтра\n"
    "• <b>📊 Наступні 7 днів</b> — завдання на найближчий тиждень\n"
    "• <b>📋 Заплановані</b> — усі завдання з датою сьогодні або в майбутньому\n"
    "• <b>✅ Виконані</b> — завдання, строк яких уже минув\n"
    "• <b>🔄 Повторювані</b> — усі активні повторювані завдання\n\n"
    "Завдання сортуються спочатку за датою, потім за пріоритетом.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>✏️ РЕДАГУВАННЯ ТА ВИДАЛЕННЯ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "У будь-якому списку поруч із кожним завданням є кнопки:\n"
    "• ✏️ <b>Редагувати</b> — змінити назву, дату або пріоритет\n"
    "• 🗑️ <b>Видалити</b> — повністю видалити завдання\n\n"
    "Якщо це був останній екземпляр повторюваного завдання — правило автоматично видалиться.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>🔍 ПОШУК</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Натисніть «🔍 Пошук» або напишіть /search, потім введіть слово або фразу.\n"
    "Я знайду всі активні завдання, у назві яких є цей текст.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>⭐ ПРИОРІТЕТИ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• 🔵 <b>Низький</b> — можна відкласти\n"
    "• 🟡 <b>Звичайний</b> — стандартний (за замовчуванням)\n"
    "• 🔴 <b>Високий</b> — терміново / важливо\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>⌨️ КОМАНДИ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• /start — головне меню\n"
    "• /add — створити завдання покроково\n"
    "• /search — пошук завдань за текстом\n"
    "• /today, /tomorrow, /week — швидкі списки\n"
    "• /planned, /done, /recurring — інші списки\n"
    "• /help — ця довідка\n"
    "• /cancel — скасувати поточну дію\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<b>💡 ПОРАДИ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• Якщо ви випадково ввели минулу дату для повторюваного завдання — "
    "я автоматично перенесу його на найближчу майбутню дату.\n"
    "• Натисніть «❌ Скасувати» у будь-який момент, щоб перервати створення.\n"
    "• Дані зберігаються у хмарній базі даних і не зникають при оновленнях.\n\n"
    "Готові? Просто напишіть своє перше завдання 👇"
)


# =============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =============================================================================

def _escape(text: str) -> str:
    return escape(str(text), quote=False)


def _parse_user_date(text: str) -> str | None:
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

    return None


def _format_due(task: dict) -> str:
    """Форматування дати/часу завдання (без іконки календаря)."""
    raw_at = task.get("due_at")
    raw_date = task.get("due_date")

    if raw_at:
        try:
            dt = datetime.fromisoformat(raw_at)
            return dt.strftime('%d.%m.%Y о %H:%M')
        except (ValueError, TypeError):
            return _escape(raw_at)

    if raw_date:
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
            return d.strftime('%d.%m.%Y')
        except (ValueError, TypeError):
            return _escape(raw_date)

    return "без строку"


def _format_task_line(task: dict, index: int = 0) -> str:
    """Форматування одного завдання для списку з нумерацією."""
    priority = PRIORITY_EMOJI.get(task.get("priority", "normal"), "🟡")
    category = "💼" if task.get("category") == "work" else "👤"

    title = _escape(task.get("title") or "Без назви")
    due = _format_due(task)
    
    # Значок повторення йде ОСТАННІМ у рядку з датою та іконками
    recurrence_mark = " 🔁" if task.get("recurrence_rule_id") else ""
    
    # Формат: дата пріоритет категорія повторення
    date_and_meta = f"{due} {priority} {category}{recurrence_mark}"
    
    if index > 0:
        return f"{index}. <b>{title}</b>\n   {date_and_meta}"
    else:
        return f"<b>{title}</b>\n   {date_and_meta}"


async def _send_tasks_list(
    message: types.Message,
    title: str,
    tasks: list[dict],
) -> None:
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
        line_size = len(_format_task_line(task, 1)) + 2

        if current and current_size + line_size > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = []
            current_size = len(title) + 20

        current.append(task)
        current_size += line_size

    if current:
        chunks.append(current)

    global_index = 0
    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) == 1:
            header = f"<b>{_escape(title)}</b> ({len(tasks)})"
        else:
            header = (
                f"<b>{_escape(title)}</b>\n"
                f"Частина {index}/{len(chunks)} · усього {len(tasks)}"
            )

        body_parts = []
        for task in chunk:
            global_index += 1
            body_parts.append(_format_task_line(task, global_index))
        
        body = "\n\n".join(body_parts)

        buttons = []
        for task in chunk:
            label = (task.get("title") or "Завдання").replace("\n", " ")[:20]
            task_id = task['id']
            buttons.append([
                types.InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"edit_menu_{task_id}"),
                types.InlineKeyboardButton(text=f"🗑️ {label}", callback_data=f"delete_{task_id}"),
            ])

        await message.answer(
            f"{header}\n\n{body}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None,
            parse_mode="HTML",
        )


async def _show_task_list(
    message: types.Message,
    state: FSMContext,
    title: str,
    fetch_func,
) -> None:
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


def _format_recurrence_line(recurrence: dict) -> str:
    """Форматування правила повторення в рядок для попереднього перегляду."""
    if not recurrence:
        return ""
    
    rule_type = recurrence.get("rule_type")
    if rule_type == "daily":
        return "\n🔁 Щодня"
    elif rule_type == "every_n_days":
        n = recurrence.get("interval_days", 1)
        return f"\n🔁 Кожні {n} дн."
    elif rule_type == "weekly":
        return "\n🔁 Щотижня"
    elif rule_type == "specific_days":
        days_str = recurrence.get("days_of_week", "")
        try:
            days = [int(d.strip()) for d in days_str.split(",") if d.strip()]
            day_names = [WEEKDAY_NAMES.get(d, str(d)) for d in days]
            return f"\n🔁 По {', '.join(day_names)}"
        except (ValueError, TypeError):
            return "\n🔁 У вибрані дні"
    elif rule_type == "monthly":
        day = recurrence.get("day_of_month")
        if day:
            return f"\n🔁 Щомісяця {day}-го"
        return "\n🔁 Щомісяця"
    elif rule_type == "every_n_months":
        n = recurrence.get("interval_months", 1)
        return f"\n🔁 Кожні {n} міс."
    elif rule_type == "yearly":
        n = recurrence.get("interval_years", 1)
        return f"\n🔁 Кожні {n} р."
    
    return ""


def _build_preview_text(data: dict) -> str:
    """Текст попереднього перегляду (без 📅)."""
    title = _escape(data.get("title") or "Без назви")
    category = CATEGORY_LABEL.get(data.get("category", "personal"), "👤 Особисте")
    priority = PRIORITY_LABEL.get(data.get("priority", "normal"), "🟡 Звичайний")

    due_line = "дату не вказано"

    if data.get("due_at"):
        try:
            dt = datetime.fromisoformat(data["due_at"])
            due_line = dt.strftime('%d.%m.%Y о %H:%M')
        except (ValueError, TypeError):
            due_line = data['due_at']
    elif data.get("due_date"):
        norm_date = _normalize_date(data.get("due_date"))
        if norm_date:
            d = datetime.strptime(norm_date, "%Y-%m-%d").date()
            due_line = d.strftime('%d.%m.%Y')
        else:
            due_line = data['due_date']

    recurrence_line = _format_recurrence_line(data.get("recurrence"))

    return (
        f"🤖 <b>Перевірте завдання:</b>\n\n"
        f"📝 <b>{title}</b>\n"
        f"{due_line}{recurrence_line}\n"
        f"{category}\n"
        f"{priority}\n\n"
        f"Все вірно? Зберегти?"
    )


def _preview_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура попереднього перегляду з кнопкою зміни дати."""
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
                text="📅 Змінити дату", callback_data="task_change_date"
            )],
            [types.InlineKeyboardButton(
                text="❌ Скасувати", callback_data="task_cancel"
            )],
        ]
    )


def _empty_inline_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[])


async def _send_preview(
    message: types.Message,
    state: FSMContext,
) -> None:
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
    data = await state.get_data()
    await callback.message.edit_text(
        _build_preview_text(data),
        reply_markup=_preview_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(TaskCreation.confirming)
    await callback.answer()


def _is_control_text(text: str) -> bool:
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
    """Показати всі активні повторювані завдання як звичайний список."""
    await _show_task_list(
        message, state, "🔄 Повторювані завдання",
        task_service.get_recurring_tasks,
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

    from app.repositories import recurrence_repository
    from app.services import recurrence_service

    recurrence_rule_id = None
    recurrence = data.get("recurrence")
    due_date = _normalize_date(data.get("due_date"))
    due_at = data.get("due_at")
    
    # Якщо є повторення і дата в минулому — обчислюємо наступну дату після сьогодні
    if recurrence and due_date:
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
            today = date.today()
            
            if due_date_obj < today:
                next_date = recurrence_service.calculate_next_date_after_today(recurrence)
                if next_date:
                    due_date = next_date.isoformat()
                    due_at = None
                    logger.info(f"Дата в минулому ({due_date_obj}), встановлено наступну: {due_date}")
        except Exception as e:
            logger.warning(f"Помилка обчислення наступної дати: {e}")

    if recurrence:
        try:
            recurrence_rule_id = await recurrence_repository.create_rule(
                rule_type=recurrence.get("rule_type"),
                interval_days=recurrence.get("interval_days"),
                days_of_week=recurrence.get("days_of_week"),
                day_of_month=recurrence.get("day_of_month"),
                execution_time=recurrence.get("execution_time"),
                interval_months=recurrence.get("interval_months"),
                interval_years=recurrence.get("interval_years"),
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
            due_at=due_at,
            due_date=due_date,
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

    if recurrence:
        recurrence_desc = _format_recurrence_line(recurrence).strip()
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


@router.callback_query(F.data == "task_change_date")
async def change_date(
    callback: types.CallbackQuery,
    state: FSMContext,
) -> None:
    """Запитати нову дату для завдання."""
    data = await state.get_data()
    if not data.get("title"):
        await callback.answer("Немає активного завдання.", show_alert=True)
        return

    await callback.message.edit_text(
        "📅 <b>Введіть нову дату у форматі ДД.ММ.РРРР</b>\n"
        "Наприклад: <code>20.10.2026</code>",
        parse_mode="HTML",
    )
    await callback.answer()
    await state.set_state(TaskCreation.waiting_for_date_change)


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


# --- ВИДАЛЕННЯ ЗАВДАННЯ ---

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
# ПОШУК ТА РЕДАГУВАННЯ
# =============================================================================

class SearchState(StatesGroup):
    waiting_for_query = State()

class EditState(StatesGroup):
    waiting_for_new_title = State()
    waiting_for_new_date = State()

# --- ПОШУК ---

@router.message(Command("search"))
@router.message(F.text == "🔍 Пошук")
async def cmd_search(message: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await message.answer(
        "🔎 <b>Пошук завдань</b>\n\n"
        "Введіть слово або фразу для пошуку в назві завдань:",
        parse_mode="HTML"
    )

@router.message(SearchState.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Запит занадто короткий. Введіть щонайменше 2 символи.")
        return
        
    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    tasks = await task_service.search_tasks(user_id, query)
    await state.clear()
    
    if not tasks:
        await message.answer(f"📭 За запитом «<b>{_escape(query)}</b>» нічого не знайдено.", parse_mode="HTML")
        return
        
    await _send_tasks_list(message, f"🔎 Результати пошуку: «{query}»", tasks)


# --- РЕДАГУВАННЯ ---

@router.callback_query(F.data.startswith("edit_menu_"))
async def open_edit_menu(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[-1])
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    task = await task_service.get_task(task_id, user_id)
    
    if not task:
        await callback.answer("Завдання не знайдено.", show_alert=True)
        return

    title = _escape(task.get("title"))
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📝 Змінити назву", callback_data=f"edit_title_{task_id}")],
        [types.InlineKeyboardButton(text="📅 Змінити дату", callback_data=f"edit_date_{task_id}")],
        [types.InlineKeyboardButton(text="⭐ Змінити пріоритет", callback_data=f"edit_priority_{task_id}")],
        [types.InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_list")],
    ])
    
    await callback.message.edit_text(
        f"✏️ <b>Редагування завдання:</b>\n\n📝 {title}\n\nОберіть, що змінити:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("edit_title_"))
async def start_edit_title(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_task_id=task_id)
    await callback.message.edit_text("Введіть <b>нову назву</b> завдання:", parse_mode="HTML")
    await callback.answer()
    await state.set_state(EditState.waiting_for_new_title)

@router.message(EditState.waiting_for_new_title)
async def process_new_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    
    new_title = message.text.strip()
    await task_repository.update_task(task_id, user_id, title=new_title)
    
    await state.clear()
    await message.answer(f"✅ Назву змінено на: <b>{_escape(new_title)}</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("edit_date_"))
async def start_edit_date(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_task_id=task_id)
    await callback.message.edit_text(
        "Введіть <b>нову дату</b> у форматі ДД.ММ.РРРР\n(наприклад, 25.10.2026):", 
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(EditState.waiting_for_new_date)

@router.message(EditState.waiting_for_new_date)
async def process_new_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    
    new_date = _parse_user_date(message.text.strip())
    if not new_date:
        await message.answer("❌ Невірний формат. Спробуйте ще раз (ДД.ММ.РРРР):")
        return
        
    await task_repository.update_task(task_id, user_id, due_date=new_date, due_at=None)
    await state.clear()
    await message.answer(f"✅ Дату змінено на: <b>{new_date}</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("edit_priority_"))
async def edit_priority_inline(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_task_id=task_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔵 Низький", callback_data="set_priority_low")],
        [types.InlineKeyboardButton(text="🟡 Звичайний", callback_data="set_priority_normal")],
        [types.InlineKeyboardButton(text="🔴 Високий", callback_data="set_priority_high")],
    ])
    await callback.message.edit_text("⭐ Оберіть новий пріоритет:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("set_priority_"))
async def process_new_priority(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    
    new_priority = callback.data.split("_")[-1]
    await task_repository.update_task(task_id, user_id, priority=new_priority)
    
    await state.clear()
    await callback.message.edit_text("✅ Пріоритет успішно змінено.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[]))
    await callback.answer("Пріоритет оновлено!")


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
async def process_due_date(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Обробка дати під час покрокового створення через /add."""
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


@router.message(TaskCreation.waiting_for_date_input)
async def process_date_input(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Обробка дати після парсингу природної мови (дата не була розпізнана)."""
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


@router.message(TaskCreation.waiting_for_date_change)
async def process_date_change(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Обробка зміни дати в попередньому перегляді."""
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
    await state.update_data(due_at=None)
    
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

    if recurrence:
        await state.update_data(recurrence=recurrence)

    if not due_date and not due_at:
        if recurrence:
            today = date.today().isoformat()
            logger.info(
                f"Для повторюваного завдання встановлено базову дату: {today}"
            )
            await state.update_data(due_date=today)
            await _send_preview(message, state)
            return
        else:
            await message.answer(
                "📅 Вкажіть дату виконання у форматі <b>ДД.ММ.РРРР</b>\n"
                "Наприклад: <code>20.10.2026</code>",
                parse_mode="HTML",
            )
            await state.set_state(TaskCreation.waiting_for_date_input)
            return

    if due_date:
        await state.update_data(due_date=due_date)
    if due_at:
        await state.update_data(due_at=due_at)

    await _send_preview(message, state)
