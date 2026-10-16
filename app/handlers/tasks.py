import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.services import task_service
from app.utils.dates import format_tasks_list
from app.repositories import user_repository

logger = logging.getLogger(__name__)
router = Router()

class TaskCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_category = State()
    waiting_for_priority = State()
    waiting_for_due_date = State()
    confirming = State()

def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Створити головне меню"""
    keyboard = [
        [types.KeyboardButton(text="➕ Додати завдання"), types.KeyboardButton(text="📅 На сьогодні")],
        [types.KeyboardButton(text="📆 На завтра"), types.KeyboardButton(text="📊 Наступні 7 днів")],
        [types.KeyboardButton(text="⚠️ Прострочені"), types.KeyboardButton(text="📝 Без строку")],
        [types.KeyboardButton(text="⏳ У роботі"), types.KeyboardButton(text="📋 Усі завдання")],
        [types.KeyboardButton(text="🔄 Повторювані"), types.KeyboardButton(text="⚙️ Налаштування")],
        [types.KeyboardButton(text="❓ Допомога")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def get_internal_user_id(telegram_id: int) -> int:
    """Допоміжна функція для отримання внутрішнього user_id"""
    user_id = await user_repository.get_user_id_by_telegram_id(telegram_id)
    if not user_id:
        raise ValueError(f"Користувача з Telegram ID {telegram_id} не знайдено в БД")
    return user_id

@router.message(Command("add"))
async def cmd_add_task(message: types.Message, state: FSMContext):
    logger.info(f"Команда /add від користувача {message.from_user.id}")
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

@router.callback_query(TaskCreation.confirming, F.data == "task_save")
async def save_task(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
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

@router.callback_query(TaskCreation.confirming, F.data == "task_cancel")
async def cancel_task_creation(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Створення завдання скасовано")
    await callback.message.answer("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    await state.clear()
    await callback.answer()

@router.message(F.text == "❌ Скасувати")
async def cancel_any_state(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Операцію скасовано\n\nОберіть дію:", reply_markup=get_main_menu_keyboard())

# --- ОБРОБНИКИ КНОПОК ГОЛОВНОГО МЕНЮ ---

@router.message(F.text == "➕ Додати завдання")
async def btn_add_task(message: types.Message, state: FSMContext):
    await cmd_add_task(message, state)

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
    # Поки що показуємо тільки активні, як найчастіше потрібні
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
        "❓ <b>Допомова korzystuvachu</b>\n\n"
        "Цей бот допомагає керувати завданнями.\n\n"
        "📌 <b>Як створити завдання:</b>\n"
        "1. Натисніть «➕ Додати завдання» або введіть /add\n"
        "2. Або просто напишіть завдання текстом (наприклад: «Завтра о 10:00 зателефонувати»)\n\n"
        "📌 <b>Команди:</b>\n"
        "/start - Головне меню\n"
        "/today - Завдання на сьогодні\n"
        "/settings - Налаштувати час звіту та часовий пояс"
    )
    await message.answer(help_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

# --- ОБРОБНИКИ ТЕКСТОВИХ КОМАНД (дублюють кнопки) ---

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
