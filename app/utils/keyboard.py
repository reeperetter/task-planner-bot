"""Головне меню бота."""

from aiogram import types


def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Створити головне меню з кнопками."""
    keyboard = [
        [types.KeyboardButton(text="➕ Додати завдання"), types.KeyboardButton(text="📅 На сьогодні")],
        [types.KeyboardButton(text="📆 На завтра"), types.KeyboardButton(text="📊 Наступні 7 днів")],
        [types.KeyboardButton(text="📋 Заплановані"), types.KeyboardButton(text="✅ Виконані")],
        [types.KeyboardButton(text="🔄 Повторювані"), types.KeyboardButton(text="❓ Допомога")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
