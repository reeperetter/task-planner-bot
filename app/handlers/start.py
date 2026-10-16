from aiogram import Router, types
from aiogram.filters import CommandStart
from app.services.user_service import register_user

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обробка команди /start"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    result = await register_user(telegram_id, username, first_name)
    
    if result["status"] == "denied":
        await message.answer(result["message"])
        return
    
    user = result["user"]
    
    if result["status"] == "created":
        welcome_text = (
            f"👋 Вітаю, {first_name or username or 'користувач'}!\n\n"
            f"Ви успішно зареєстровані в системі.\n\n"
            f"📋 <b>Основні команди:</b>\n"
            f"/add - Додати завдання\n"
            f"/today - Завдання на сьогодні\n"
            f"/tomorrow - Завдання на завтра\n"
            f"/week - Завдання на наступні 7 днів\n"
            f"/overdue - Прострочені завдання\n"
            f"/settings - Налаштування\n"
            f"/help - Інструкція\n\n"
            f"💡 Ви також можете створювати завдання звичайним текстом, наприклад:\n"
            f"• «Завтра о 10:00 зателефонувати постачальнику»\n"
            f"• «На п'ятницю підготувати звіт, робота»\n"
            f"• «Купити лампочки»"
        )
    else:
        welcome_text = (
            f"👋 З поверненням, {first_name or username or 'користувач'}!\n\n"
            f"📋 <b>Основні команди:</b>\n"
            f"/add - Додати завдання\n"
            f"/today - Завдання на сьогодні\n"
            f"/tomorrow - Завдання на завтра\n"
            f"/week - Завдання на наступні 7 днів\n"
            f"/overdue - Прострочені завдання\n"
            f"/settings - Налаштування\n"
            f"/help - Інструкція"
        )
    
    await message.answer(welcome_text, parse_mode="HTML")
