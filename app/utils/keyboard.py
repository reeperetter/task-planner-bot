from aiogram import types

def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = [
        [types.KeyboardButton(text="➕ Додати завдання"), types.KeyboardButton(text="🔍 Пошук")],
        [types.KeyboardButton(text="📅 На сьогодні"), types.KeyboardButton(text="📆 На завтра")],
        [types.KeyboardButton(text="📊 Наступні 7 днів"), types.KeyboardButton(text="🔄 Повторювані")],
        [types.KeyboardButton(text="📋 Заплановані"), types.KeyboardButton(text="✅ Виконані")],
        [types.KeyboardButton(text="❓ Допомога")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
