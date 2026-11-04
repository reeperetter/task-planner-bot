"""Фоновий планувальник для нагадувань."""

import asyncio
import logging
from app.repositories import task_repository

logger = logging.getLogger(__name__)

async def start_reminder_scheduler(bot):
    """Запускає нескінченний цикл перевірки нагадувань кожну хвилину."""
    logger.info("🕒 Запуск фонового планувальника нагадувань...")
    
    while True:
        try:
            # Чекаємо 60 секунд між перевірками
            await asyncio.sleep(60)
            await _check_upcoming_tasks(bot)
            
        except asyncio.CancelledError:
            logger.info("🕒 Планувальник зупинено.")
            break
        except Exception as e:
            logger.error(f"❌ Критична помилка в планувальнику: {e}", exc_info=True)


async def _check_upcoming_tasks(bot):
    """Перевіряє та надсилає нагадування про завдання за 1 годину."""
    reminders = await task_repository.get_upcoming_reminders()
    
    if not reminders:
        return
        
    logger.info(f"🔔 Знайдено {len(reminders)} завдань для нагадування.")
    
    for rem in reminders:
        try:
            due_time = rem['due_at'].strftime('%H:%M')
            message_text = (
                f"⏰ <b>Нагадування:</b>\n\n"
                f"📝 {rem['title']}\n"
                f"🕒 Час: {due_time}\n\n"
                f"Не забудьте виконати!"
            )
            
            await bot.send_message(rem['telegram_id'], message_text, parse_mode="HTML")
            
            # Позначаємо, що нагадали, щоб не спамити при перезапуску
            await task_repository.mark_task_notified(rem['id'])
            logger.info(f"✅ Нагадування надіслано: task_id={rem['id']}, user={rem['telegram_id']}")
            
        except Exception as e:
            logger.error(f"Не вдалося надіслати нагадування для task_id={rem['id']}: {e}")
