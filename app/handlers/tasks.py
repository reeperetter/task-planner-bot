import logging
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.services import task_service
from app.services.parser_service import parse_natural_language
from app.utils.dates import format_tasks_list
from app.utils.keyboard import get_main_menu_keyboard
from app.repositories import user_repository

logger = logging.getLogger(__name__)
router = Router()

class TaskCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_category = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()
    confirming = State()

async def get_internal_user_id(telegram_id: int) -> int:
    """Допоміжна функція для отримання внутрішнього user_id"""
    user_id = await user_repository.get_user_id_by_telegram_id(telegram_id)
    if not user_id:
        raise ValueError(f"Користувача з Telegram ID {telegram_id} не знайдено в БД")
    return user_id

# --- CALLBACK QUERY HANDLERS (БЕЗ ФІЛЬТРУ СТАНУ!) ---

@router.callback_query(F.data == "task_save")
async def save_task(callback: types.CallbackQuery, state: FSMContext):
    """Збереження завдання"""
    logger.info(f"Callback task_save від {callback.from_user.id}")
    data = await state.get_data()

    if not data:
        await callback.answer("❌ Дані не знайдено", show_alert=True)
        return

    user_id = await get_internal_user_id(callback.from_user.id)

    result = await task_service.create_task(
        user_id=user_id,
        title=data['title'],
        category=data['category'],
        priority=data['priority'],
        due_date=data.get('due_date')
    )

    await callback.message.edit_text(
        f"✅ {result['message']}\n\n"
        f"ID завдання: {result.get('task_id')}",
        parse_mode="HTML"
    )

    await callback.message.answer("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "task_edit_manual")
async def edit_manual(callback: types.CallbackQuery, state: FSMContext):
    """Якщо користувач ввів текст, але хоче змінити параметри вручну"""
    logger.info(f"Callback task_edit_manual від {callback.from_user.id}")
    await callback.message.edit_text("✏️ Давайте налаштуємо завдання вручну.")
    await callback.answer()

    data = await state.get_data()
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="👤 Особисте"), types.KeyboardButton(text="💼 Робоче")],
            [types.KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True
    )
    await callback.message.answer(
        f"Поточна назва: <b>{data.get('title', 'Без назви')}</b>\n\nОберіть категорію:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(TaskCreation.waiting_for_category)

@router.callback_query(F.data == "task_cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    """Скасування створення завдання"""
    logger.info(f"Callback task_cancel від {callback.from_user.id}")
    await callback.message.edit_text("❌ Створення завдання скасовано")
    await callback.message.answer("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await callback.answer()

# --- СТАНДАРТНИЙ ПОТОК СТВОРЕННЯ (через кнопку /add) ---

@router.message(Command("add"))
@router.message(F.text == "➕ Додати завдання")
async def cmd_add_task(message: types.Message, state: FSMContext):
    logger.info(f"Запуск інтерактивного створення завдання користувачем {message.from_user.id}")
    await message.answer(
        "✍️ <b>Створення завдання</b>\n\n"
        "Введіть назву завдання:",
        parse_mode="HTML"
    )
    await state.set_state(TaskCreation.waiting_for_title)

@router.message(TaskCreation.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Назва не може бути порожньою. Спробуйте ще раз:")
        return

    await state.update_data(title=title)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="👤 Особисте"), types.KeyboardButton(text="💼 Робоче")],
            [types.KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True
    )
    await message.answer("Оберіть категорію:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TaskCreation.waiting_for_category)

@router.message(TaskCreation.waiting_for_category, F.text.in_(["👤 Особисте", "💼 Робоче"]))
async def process_category(message: types.Message, state: FSMContext):
    category = "personal" if "Особисте" in message.text else "work"
    await state.update_data(category=category)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔵 Низький"), types.KeyboardButton(text="🟡 Звичайний"), types.KeyboardButton(text="🔴 Високий")],
            [types.KeyboardButton(text="❌ Скасувати")]
        ],
        resize_keyboard=True
    )
    await message.answer("Оберіть пріоритет:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TaskCreation.waiting_for_priority)

@router.message(TaskCreation.waiting_for_priority, F.text.in_(["🔵 Низький", "🟡 Звичайний", "🔴 Високий"]))
async def process_priority(message: types.Message, state: FSMContext):
    priority_map = {"🔵 Низький": "low", "🟡 Звичайний": "normal", "🔴 Високий": "high"}
    await state.update_data(priority=priority_map[message.text])

    await message.answer(
        "📅 Введіть дату виконання у форматі <b>ДД.ММ.РРРР</b> (наприклад, 20.10.2026)\n"
        "Або надішліть «без строку»:",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(TaskCreation.waiting_for_due_date)

@router.message(TaskCreation.waiting_for_due_date)
async def process_due_date(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    due_date = None

    if text != "без строку":
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(text, "%d.%m.%Y")
            due_date = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            await message.answer(
                "❌ Невірний формат дати.\n\n"
                "Використайте формат ДД.ММ.РРРР (наприклад, 20.10.2026)\n"
                "Або надішліть «без строку»:"
            )
            return

    await state.update_data(due_date=due_date)
    data = await state.get_data()

    category_text = "👤 Особисте" if data['category'] == 'personal' else "💼 Робоче"
    priority_map = {"low": "🔵 Низький", "normal": "🟡 Звичайний", "high": "🔴 Високий"}

    if data['due_date']:
        from datetime import datetime
        dt = datetime.strptime(data['due_date'], "%Y-%m-%d")
        due_text = f"📅 {dt.strftime('%d.%m.%Y')}"
    else:
        due_text = "📅 без строку"

    preview = (
        f"<b>Попередній перегляд завдання:</b>\n\n"
        f"📝 Назва: {data['title']}\n"
        f"{category_text}\n"
        f"{priority_map[data['priority']]}\n"
        f"{due_text}\n\n"
        f"Зберегти завдання?"
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Зберегти", callback_data="task_save")],
        [types.InlineKeyboardButton(text="❌ Скасувати", callback_data="task_cancel")]
    ])

    await message.answer(preview, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TaskCreation.confirming)

@router.message(F.text == "❌ Скасувати")
async def cancel_message(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Операцію скасовано\n\nОберіть дію:", reply_markup=get_main_menu_keyboard())

# --- ОБРОБНИКИ КНОПОК ГОЛОВНОГО МЕНЮ ---

@router.message(F.text == "📅 На сьогодні")
async def btn_today(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_today(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на сьогодні"), parse_mode="HTML")

@router.message(F.text == "📆 На завтра")
async def btn_tomorrow(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_tomorrow(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на завтра"), parse_mode="HTML")

@router.message(F.text == "📊 Наступні 7 днів")
async def btn_week(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_week(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на наступні 7 днів"), parse_mode="HTML")

@router.message(F.text == "⚠️ Прострочені")
async def btn_overdue(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_overdue_tasks(user_id)
    await message.answer(format_tasks_list(tasks, "⚠️ Прострочені завдання"), parse_mode="HTML")

@router.message(F.text == "⏳ У роботі")
async def btn_active(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_active_tasks(user_id)
    await message.answer(format_tasks_list(tasks, "⏳ Усі активні завдання"), parse_mode="HTML")

@router.message(F.text == "📝 Без строку")
async def btn_no_deadline(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_without_due_date(user_id)
    await message.answer(format_tasks_list(tasks, "📝 Завдання без строку"), parse_mode="HTML")

@router.message(F.text == "📋 Усі завдання")
async def btn_all_tasks(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_active_tasks(user_id)
    await message.answer(format_tasks_list(tasks, "📋 Усі активні завдання"), parse_mode="HTML")

@router.message(F.text == "🔄 Повторювані")
async def btn_recurring(message: types.Message):
    await message.answer("🔄 Функція повторюваних завдань знаходиться в розробці (Етап 5).", reply_markup=get_main_menu_keyboard())

@router.message(F.text == "⚙️ Налаштування")
async def btn_settings(message: types.Message):
    await message.answer("⚙️ Функція налаштувань знаходиться в розробці (Етап 7).", reply_markup=get_main_menu_keyboard())

@router.message(F.text == "❓ Допомога")
async def btn_help(message: types.Message):
    help_text = (
        "❓ <b>Допомога користувачу</b>\n\n"
        "Цей бот допомагає керувати завданнями.\n\n"
        "📌 <b>Як створити завдання:</b>\n"
        "1. Просто напишіть текст, наприклад: «Завтра о 10:00 зателефонувати, робота»\n"
        "2. Або натисніть «➕ Додати завдання» для покрокового створення.\n\n"
        "📌 <b>Команди:</b>\n"
        "/start - Головне меню\n"
        "/today - Завдання на сьогодні\n"
        "/settings - Налаштувати час звіту та часовий пояс"
    )
    await message.answer(help_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

# --- ТЕКСТОВІ КОМАНДИ (дублюють кнопки) ---

@router.message(Command("today"))
async def cmd_today(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_today(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на сьогодні"), parse_mode="HTML")

@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_tomorrow(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на завтра"), parse_mode="HTML")

@router.message(Command("week"))
async def cmd_week(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_tasks_week(user_id)
    await message.answer(format_tasks_list(tasks, "📅 Завдання на наступні 7 днів"), parse_mode="HTML")

@router.message(Command("overdue"))
async def cmd_overdue(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_overdue_tasks(user_id)
    await message.answer(format_tasks_list(tasks, "⚠️ Прострочені завдання"), parse_mode="HTML")

@router.message(Command("active"))
async def cmd_active(message: types.Message):
    user_id = await get_internal_user_id(message.from_user.id)
    tasks = await task_service.get_active_tasks(user_id)
    await message.answer(format_tasks_list(tasks, "⏳ Усі активні завдання"), parse_mode="HTML")

# --- НОВИЙ ОБРОБНИК: Природна мова (В САМОМУ КІНЦІ!) ---

@router.message(F.text, StateFilter(None))
async def handle_natural_language_task(message: types.Message, state: FSMContext):
    """Обробка звичайного текстового повідомлення як спроби створити завдання"""
    text = message.text.strip()

    if text.startswith('/'):
        return

    logger.info(f"Спроба створення завдання з природної мови: '{text}'")

    parsed = parse_natural_language(text)

    await state.update_data(
        title=parsed["title"],
        category=parsed["category"],
        priority=parsed["priority"],
        due_date=parsed["due_date"]
    )

    category_text = "👤 Особисте" if parsed["category"] == "personal" else "💼 Робоче"
    priority_map = {"low": "🔵 Низький", "normal": "🟡 Звичайний", "high": "🔴 Високий"}
    priority_text = priority_map[parsed["priority"]]

    if parsed["due_date"]:
        due_text = f"📅 {parsed['due_date']}"
    else:
        due_text = "📅 без строку"

    preview = (
        f"🤖 <b>Я зрозумів ваше завдання так:</b>\n\n"
        f"📝 Назва: {parsed['title']}\n"
        f"{category_text}\n"
        f"{priority_text}\n"
        f"{due_text}\n\n"
        f"Все вірно? Зберегти завдання?"
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Зберегти", callback_data="task_save")],
        [types.InlineKeyboardButton(text="✏️ Змінити вручну", callback_data="task_edit_manual")],
        [types.InlineKeyboardButton(text="❌ Скасувати", callback_data="task_cancel")]
    ])

    await message.answer(preview, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TaskCreation.confirming)
    logger.info(f"Встановлено стан: confirming")
