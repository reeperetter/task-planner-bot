from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository

class SchedulerService:
    def __init__(self, bot: Bot, task_repo: TaskRepository, user_repo: UserRepository):
        self.bot = bot
        self.task_repo = task_repo
        self.user_repo = user_repo
        # Явно вказуємо київську часову зону для уникнення розсинхронізації часу
        self.scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

    def start(self):
        """Ініціалізація та запуск фонового планувальника задач."""
        
        # 1. Ранковий дайджест задач на день (спрацьовує щодня о 08:00)
        self.scheduler.add_job(
            self.send_morning_digest,
            "cron",
            hour=8,
            minute=0,
            id="morning_digest_job",
            replace_existing=True
        )

        # 2. Нагадування за годину до події (перевірка кожної хвилини)
        self.scheduler.add_job(
            self.send_hourly_reminders,
            "interval",
            minutes=1,
            id="hourly_reminders_job",
            replace_existing=True
        )

        self.scheduler.start()

    async def send_morning_digest(self):
        """Формування та відправка ранкового списку задач усім користувачам."""
        try:
            users = await self.user_repo.get_all_users()
            today = datetime.now().date()

            for user in users:
                tasks = await self.task_repo.get_tasks_by_date(user.id, today)
                if not tasks:
                    continue

                text = f"🌅 **Доброго ранку! твої задачі на сьогодні ({today.strftime('%d.%m.%Y')}):**\n\n"
                for task in tasks:
                    time_str = task.time.strftime('%H:%M') if hasattr(task.time, 'strftime') else str(task.time)
                    text += f"• `{time_str}` — {task.title}\n"

                await self.bot.send_message(user.telegram_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"Помилка у ранковому дайджесті: {e}")

    async def send_hourly_reminders(self):
        """Перевірка подій, які настануть приблизно через годину, та відправка сповіщень."""
        try:
            now = datetime.now()
            # Формуємо часовий діапазон у межах одної хвилини для точного спрацьовування
            target_time_start = now + timedelta(minutes=59)
            target_time_end = now + timedelta(minutes=61)

            tasks = await self.task_repo.get_tasks_in_time_range(target_time_start, target_time_end)

            for task in tasks:
                text = f"⏰ **Нагадування!**\nПодія **«{task.title}»** розпочнеться приблизно за годину."
                
                # Отримуємо telegram_id користувача (залежно від структури зв'язків у моделі)
                user_id = getattr(task, 'telegram_id', None)
                if not user_id and hasattr(task, 'user_id'):
                    user = await self.user_repo.get_by_id(task.user_id)
                    user_id = user.telegram_id if user else None

                if user_id:
                    await self.bot.send_message(user_id, text, parse_mode="Markdown")
                    
                    # Позначаємо задачу як нагадувану, щоб уникнути дублювання
                    if hasattr(self.task_repo, 'mark_as_reminded'):
                        await self.task_repo.mark_as_reminded(task.id)
        except Exception as e:
            print(f"Помилка при перевірці нагадувань за годину: {e}")
