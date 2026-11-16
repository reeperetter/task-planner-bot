"""Обробники налаштувань нагадувань та ранкового дайджесту."""

import logging
import re
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.repositories import user_repository, settings_repository
from app.utils.keyboard import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


class SettingsState(StatesGroup):
    waiting_for_morning_time = State()
    waiting_for_reminder_minutes = State()


def _format_minutes_label(minutes: int) -> str:
    if minutes <= 0:
        return "вимкнено"
    if minutes < 60:
        return f"за {minutes} хв"
    if minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return "за 1 год (60 хв)"
        return f"за {hours} год ({minutes} хв)"
    return f"за {minutes // 60} год {minutes % 60} хв"


def _build_settings_view(settings: dict) -> tuple[str, types.InlineKeyboardMarkup]:
    morning_enabled = bool(settings.get("morning_report_enabled", 1))
    morning_time = settings.get("morning_report_time", "08:00")
    reminder_enabled = bool(settings.get("reminder_enabled", 1))
    reminder_minutes = int(settings.get("reminder_minutes_before", 60))
    tz = settings.get("timezone", "Europe/Kyiv")

    morning_status = f"✅ Увімкнено (о <b>{morning_time}</b>)" if morning_enabled else "❌ Вимкнено"
    reminder_status = (
        f"✅ Увімкнено (<b>{_format_minutes_label(reminder_minutes)}</b>)"
        if reminder_enabled
        else "❌ Вимкнено"
    )

    text = (
        "⚙️ <b>Налаштування сповіщень</b>\n\n"
        f"🌅 <b>Ранковий дайджест запланованих задач:</b>\n"
        f"   {morning_status}\n\n"
        f"⏰ <b>Нагадування перед завданням (з вказаним часом):</b>\n"
        f"   {reminder_status}\n\n"
        f"🌍 <b>Часовий пояс:</b> <code>{tz}</code>\n\n"
        "Оберіть параметр для зміни:"
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🌅 Час ранкового дайджесту",
                    callback_data="settings_morning_time",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔕 Вимкнути ранковий дайджест" if morning_enabled else "🔔 Увімкнути ранковий дайджест",
                    callback_data="settings_toggle_morning",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⏰ Інтервал нагадування до події",
                    callback_data="settings_reminder_interval",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔕 Вимкнути нагадування до події" if reminder_enabled else "🔔 Увімкнути нагадування до події",
                    callback_data="settings_toggle_reminder",
                )
            ],
        ]
    )
    return text, keyboard


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Налаштування")
async def cmd_settings(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    if user_id is None:
        await message.answer(
            "👋 Спочатку натисніть /start, щоб зареєструватися.",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    settings = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(settings)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "settings_back")
async def settings_back(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    settings = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(settings)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "settings_toggle_morning")
async def toggle_morning(callback: types.CallbackQuery) -> None:
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    settings = await settings_repository.get_user_settings(user_id)
    new_val = 0 if settings.get("morning_report_enabled", 1) else 1
    await settings_repository.update_user_settings(user_id, morning_report_enabled=new_val)

    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("Налаштування оновлено")


@router.callback_query(F.data == "settings_toggle_reminder")
async def toggle_reminder(callback: types.CallbackQuery) -> None:
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    settings = await settings_repository.get_user_settings(user_id)
    new_val = 0 if settings.get("reminder_enabled", 1) else 1
    await settings_repository.update_user_settings(user_id, reminder_enabled=new_val)

    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("Налаштування оновлено")


@router.callback_query(F.data == "settings_morning_time")
async def ask_morning_time(callback: types.CallbackQuery, state: FSMContext) -> None:
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="07:00", callback_data="set_mtime_07:00"),
                types.InlineKeyboardButton(text="08:00", callback_data="set_mtime_08:00"),
                types.InlineKeyboardButton(text="09:00", callback_data="set_mtime_09:00"),
            ],
            [
                types.InlineKeyboardButton(text="10:00", callback_data="set_mtime_10:00"),
                types.InlineKeyboardButton(text="↩️ Назад", callback_data="settings_back"),
            ],
        ]
    )
    await callback.message.edit_text(
        "🌅 <b>Час ранкового дайджесту</b>\n\n"
        "Оберіть готовий варіант кнопкою або введіть свій час у форматі <b>ГГ:ХХ</b> (наприклад, <code>07:30</code>):",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(SettingsState.waiting_for_morning_time)
    await callback.answer()


@router.callback_query(F.data.startswith("set_mtime_"))
async def set_morning_time_preset(callback: types.CallbackQuery, state: FSMContext) -> None:
    time_str = callback.data.replace("set_mtime_", "")
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    await settings_repository.update_user_settings(
        user_id, morning_report_time=time_str, morning_report_enabled=1
    )
    await state.clear()
    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer(f"Час дайджесту: {time_str}")


@router.message(SettingsState.waiting_for_morning_time)
async def process_morning_time_input(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", raw)
    if not match:
        await message.answer(
            "❌ Невірний формат часу. Введіть час як <b>ГГ:ХХ</b> (наприклад, <code>08:15</code>) або натисніть /cancel:",
            parse_mode="HTML",
        )
        return

    hour, minute = int(match.group(1)), int(match.group(2))
    formatted = f"{hour:02d}:{minute:02d}"

    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    if user_id is None:
        await state.clear()
        await message.answer("Спочатку натисніть /start.")
        return

    await settings_repository.update_user_settings(
        user_id, morning_report_time=formatted, morning_report_enabled=1
    )
    await state.clear()

    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await message.answer(
        f"✅ Час ранкового дайджесту встановлено на <b>{formatted}</b>.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "settings_reminder_interval")
async def ask_reminder_interval(callback: types.CallbackQuery, state: FSMContext) -> None:
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="За 15 хв", callback_data="set_rem_15"),
                types.InlineKeyboardButton(text="За 30 хв", callback_data="set_rem_30"),
                types.InlineKeyboardButton(text="За 1 год", callback_data="set_rem_60"),
            ],
            [
                types.InlineKeyboardButton(text="За 2 год", callback_data="set_rem_120"),
                types.InlineKeyboardButton(text="За 3 год", callback_data="set_rem_180"),
                types.InlineKeyboardButton(text="↩️ Назад", callback_data="settings_back"),
            ],
        ]
    )
    await callback.message.edit_text(
        "⏰ <b>За скільки часу нагадувати про завдання?</b>\n\n"
        "Оберіть готовий інтервал кнопкою або введіть кількість хвилин числом (від <code>1</code> до <code>1440</code>, наприклад <code>45</code>):",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(SettingsState.waiting_for_reminder_minutes)
    await callback.answer()


@router.callback_query(F.data.startswith("set_rem_"))
async def set_reminder_preset(callback: types.CallbackQuery, state: FSMContext) -> None:
    minutes = int(callback.data.replace("set_rem_", ""))
    user_id = await user_repository.get_user_id_by_telegram_id(callback.from_user.id)
    if user_id is None:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    await settings_repository.update_user_settings(
        user_id, reminder_minutes_before=minutes, reminder_enabled=1
    )
    await state.clear()
    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer(f"Інтервал: {minutes} хв")


@router.message(SettingsState.waiting_for_reminder_minutes)
async def process_reminder_minutes_input(message: types.Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 1440):
        await message.answer(
            "❌ Введіть ціле число хвилин від <b>1</b> до <b>1440</b> (наприклад, <code>45</code>) або натисніть /cancel:",
            parse_mode="HTML",
        )
        return

    minutes = int(raw)
    user_id = await user_repository.get_user_id_by_telegram_id(message.from_user.id)
    if user_id is None:
        await state.clear()
        await message.answer("Спочатку натисніть /start.")
        return

    await settings_repository.update_user_settings(
        user_id, reminder_minutes_before=minutes, reminder_enabled=1
    )
    await state.clear()

    updated = await settings_repository.get_user_settings(user_id)
    text, keyboard = _build_settings_view(updated)
    await message.answer(
        f"✅ Нагадування встановлено: <b>{_format_minutes_label(minutes)}</b>.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
