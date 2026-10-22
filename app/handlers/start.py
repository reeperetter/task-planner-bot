"""Обробник команди /start."""

from aiogram import Router, types
from aiogram.filters import CommandStart
from app.services.user_service import register_user
from app.utils.keyboard import get_main_menu_keyboard

router = Router()

WELCOME_NEW = (
    "👋 <b>Вітаю! Я — ваш особистий планувальник.</b>\n\n"
    "Я розумію природну мову. Просто напишіть мені завдання, і я сам розпізнаю деталі:\n"
    "• <code>завтра о 10:00 зустріч з клієнтом</code>\n"
    "• <code>щоп'ятниці здавати звіт</code>\n"
    "• <code>кожні 3 дні поливати квіти</code>\n\n"
    "Або натисніть «➕ Додати завдання», і я проведу вас через процес покроково.\n\n"
    "Спробуйте написати будь-яке завдання прямо зараз 👇"
)

WELCOME_BACK = (
    "👋 <b>З поверненням!</b>\n\n"
    "Напишіть нове завдання текстом або оберіть дію з меню нижче 👇"
)

@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    result = await register_user(telegram_id, username, first_name)

    if result["status"] == "denied":
        await message.answer(result["message"])
        return

    text = WELCOME_NEW if result["status"] == "created" else WELCOME_BACK

    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
