import logging
from html import escape
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.utils.dates import today_kyiv

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, bot: Bot, task_repo: TaskRepository, user_repo: UserRepository):
        self.bot = bot
        self.task_repo = task_repo
        self.user_repo = user_repo
        self.scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

    def start(self) -> None:
        """Ініціалізація та запуск фонового планувальника задач."""
        self.scheduler.add_job(
            self.send_morning_digest,
            "cron",
            hour=8,
            minute=0,
            id="morning_digest_job",
            replace_existing=True,
            misfire_grace_time=300,
        )

        self.scheduler.add_job(
            self.send_hourly_reminders,
            "interval",
            minutes=1,
            id="hourly_reminders_job",
            replace_existing=True,
            misfire_grace_time=30,
        )

        self.scheduler.start()

    def shutdown(self) -> None:
        """Зупинка планувальника."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def send_morning_digest(self) -> None:
        """Формування та відправка ранкового списку задач усім активним користувачам."""
        try:
            users = await self.user_repo.get_all_users()
            today = today_kyiv()

            for user in users:
                user_id = user["id"]
                telegram_id = user["telegram_id"]

                tasks = await self.task_repo.get_tasks_by_date(user_id, today)
                if not tasks:
                    continue

                lines = [
                    f"🌅 <b>Доброго ранку! Ваші завдання на сьогодні ({today.strftime('%d.%m.%Y')}):</b>\n"
                ]
                for task in tasks:
                    due_at = task.get("due_at")
                    time_str = due_at.strftime("%H:%M") if due_at else "протягом дня"
                    title = escape(str(task.get("title") or "Без назви"), quote=False)
                    lines.append(f"• <code>{time_str}</code> — {title}")

                text = "\n".join(lines)
                try:
                    await self.bot.send_message(telegram_id, text, parse_mode="HTML")
                except TelegramForbiddenError:
                    logger.warning(f"Користувач telegram_id={telegram_id} заблокував бота.")
                except TelegramBadRequest as e:
                    logger.error(f"Помилка Telegram API для telegram_id={telegram_id}: {e}")
        except Exception:
            logger.exception("Помилка у ранковому дайджесті")

    async def send_hourly_reminders(self) -> None:
        """Перевірка подій, які настануть протягом найближчих 60 хвилин, та відправка сповіщень."""
        try:
            tasks = await self.task_repo.get_upcoming_reminders()

            for task in tasks:
                telegram_id = task.get("telegram_id")
                if not telegram_id:
                    continue

                due_at = task.get("due_at")
                time_hint = f" о <b>{due_at.strftime('%H:%M')}</b>" if due_at else ""
                title = escape(str(task.get("title") or "Без назви"), quote=False)
                text = (
                    f"⏰ <b>Нагадування!</b>\n"
                    f"Завдання «<b>{title}</b>» розпочнеться{time_hint} (менш ніж за годину)."
                )

                try:
                    await self.bot.send_message(telegram_id, text, parse_mode="HTML")
                    await self.task_repo.mark_as_reminded(task["id"])
                except TelegramForbiddenError:
                    logger.warning(f"Користувач telegram_id={telegram_id} заблокував бота.")
                    await self.task_repo.mark_as_reminded(task["id"])
                except TelegramBadRequest as e:
                    logger.error(f"Помилка відправки нагадування для task_id={task['id']}: {e}")
        except Exception:
            logger.exception("Помилка при перевірці нагадувань за годину")
