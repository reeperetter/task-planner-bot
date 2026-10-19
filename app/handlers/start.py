"""Обробник команди /start — привітальне повідомлення."""

from aiogram import Router, types
from aiogram.filters import CommandStart
from app.services.user_service import register_user
from app.utils.keyboard import get_main_menu_keyboard

router = Router()

# Дуже коротке привітання для НОВОГО користувача
WELCOME_NEW = (
    "👋 Вітаю! Я — ваш особистий планувальник.\n\n"
    "Просто напишіть завдання текстом, і я зрозумію дату, час і повторення:\n"
    "• <code>завтра о 10:00 зустріч з клієнтом</code>\n"
    "• <code>щопонеділка тренування</code>\n"
    "• <code>кожні 3 дні поливати квіти</code>\n\n"
    "Або натисніть «➕ Додати завдання» — я запитаю по кроках.\n\n"
    "Спробуйте просто написати будь-яке завдання 👇"
)

# Коротке привітання для ПОВЕРНУТОГО користувача
WELCOME_BACK = (
    "👋 З поверненням!\n\n"
    "Напишіть нове завдання або оберіть дію з меню 👇"
)


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """Обробка команди /start."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    result = await register_user(telegram_id, username, first_name)

    if result["status"] == "denied":
        await message.answer(result["message"])
        return

    if result["status"] == "created":
        text = WELCOME_NEW
    else:
        text = WELCOME_BACK

    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
