import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.utils.dates import KYIV_TZ

logger = logging.getLogger(__name__)


def _format_minutes_human(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return "1 годину"
        elif hours in (2, 3, 4):
            return f"{hours} години"
        return f"{hours} годин"
    return f"{minutes} хв"


class SchedulerService:
    def __init__(self, bot: Bot, task_repo: TaskRepository, user_repo: UserRepository):
        self.bot = bot
        self.task_repo = task_repo
        self.user_repo = user_repo
        self.scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

    def start(self) -> None:
        """Ініціалізація та запуск фонового планувальника задач."""
        # Перевіряємо щохвилини індивідуальний час ранкового дайджесту кожного користувача
        self.scheduler.add_job(
            self.send_morning_digest,
            "interval",
            minutes=1,
            id="morning_digest_job",
            replace_existing=True,
            misfire_grace_time=30,
        )

        # Перевіряємо щохвилини нагадування до початку завдання згідно з індивідуальним інтервалом
        self.scheduler.add_job(
            self.send_upcoming_reminders,
            "interval",
            minutes=1,
            id="upcoming_reminders_job",
            replace_existing=True,
            misfire_grace_time=30,
        )

        self.scheduler.start()

    def shutdown(self) -> None:
        """Зупинка планувальника."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def send_morning_digest(self) -> None:
        """
        Відправка ранкового дайджесту кожному активному користувачу у його індивідуальний час
        (`morning_report_time`), із захистом від повторної відправки через `report_log`.
        """
        try:
            users = await self.user_repo.get_all_users()

            for user in users:
                if not user.get("morning_report_enabled", 1):
                    continue

                user_id = user["id"]
                telegram_id = user["telegram_id"]
                tz_name = user.get("timezone") or "Europe/Kyiv"
                try:
                    user_tz = ZoneInfo(tz_name)
                except Exception:
                    user_tz = KYIV_TZ

                now_user = datetime.now(user_tz)
                today_user = now_user.date()

                report_time_str = (user.get("morning_report_time") or "08:00").strip()
                try:
                    target_hour, target_minute = map(int, report_time_str.split(":"))
                except ValueError:
                    target_hour, target_minute = 8, 0

                # Спрацьовуємо, коли настав або щойно минув заданий час у межах поточної доби
                now_minutes = now_user.hour * 60 + now_user.minute
                target_minutes = target_hour * 60 + target_minute
                if now_minutes < target_minutes:
                    continue

                # Перевіряємо, чи звіт за сьогодні вже був успішно надісланий
                if await self.task_repo.was_morning_report_sent(user_id, today_user):
                    continue

                tasks_with_date = await self.task_repo.get_tasks_by_date(user_id, today_user)
                tasks_no_date = await self.task_repo.get_tasks_without_due_date(user_id)
                tasks = tasks_with_date + tasks_no_date

                if not tasks:
                    # Позначаємо як оброблене, щоб не перевіряти БД кожну хвилину до кінця дня
                    await self.task_repo.log_morning_report(user_id, today_user, status="success")
                    continue

                priority_icon = {"high": "🔴", "normal": "🟡", "low": "🔵"}
                lines = [
                    f"🌅 <b>Доброго ранку! Ваші завдання на сьогодні ({today_user.strftime('%d.%m.%Y')}):</b>\n"
                ]
                for task in tasks:
                    due_at = task.get("due_at")
                    if due_at:
                        time_str = due_at.strftime("%H:%M")
                    elif task.get("due_date"):
                        time_str = "протягом дня"
                    else:
                        time_str = "без строку"
                    p_icon = priority_icon.get(task.get("priority", "normal"), "🟡")
                    title = escape(str(task.get("title") or "Без назви"), quote=False)
                    lines.append(f"• {p_icon} <code>{time_str}</code> — {title}")

                text = "\n".join(lines)
                try:
                    await self.bot.send_message(telegram_id, text, parse_mode="HTML")
                    await self.task_repo.log_morning_report(user_id, today_user, status="success")
                except TelegramForbiddenError:
                    logger.warning(f"Користувач telegram_id={telegram_id} заблокував бота.")
                    await self.task_repo.log_morning_report(
                        user_id, today_user, status="failed", error_message="Bot blocked by user"
                    )
                except TelegramBadRequest as e:
                    logger.error(f"Помилка Telegram API для telegram_id={telegram_id}: {e}")
                    await self.task_repo.log_morning_report(
                        user_id, today_user, status="failed", error_message=str(e)
                    )
        except Exception:
            logger.exception("Помилка у ранковому дайджесті")

    async def send_upcoming_reminders(self) -> None:
        """Перевірка подій, які настануть через налаштований користувачем інтервал, та відправка сповіщень."""
        try:
            tasks = await self.task_repo.get_upcoming_reminders()

            for task in tasks:
                telegram_id = task.get("telegram_id")
                if not telegram_id:
                    continue

                due_at = task.get("due_at")
                minutes_before = int(task.get("reminder_minutes_before") or 60)
                human_interval = _format_minutes_human(minutes_before)
                time_hint = f" о <b>{due_at.strftime('%H:%M')}</b>" if due_at else ""
                title = escape(str(task.get("title") or "Без назви"), quote=False)
                text = (
                    f"⏰ <b>Нагадування!</b>\n"
                    f"Завдання «<b>{title}</b>» розпочнеться{time_hint} (через {human_interval} або менше)."
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
            logger.exception("Помилка при перевірці попередніх нагадувань")
