"""Парсер природної мови для створення завдань."""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    "пн": 1, "пон": 1, "понед": 1, "понеділок": 1, "понеділка": 1, "понеділку": 1,
    "вт": 2, "вів": 2, "вівтор": 2, "вівторок": 2, "вівторка": 2, "вівторку": 2,
    "ср": 3, "сер": 3, "серед": 3, "середа": 3, "середу": 3, "середи": 3,
    "чт": 4, "чет": 4, "четвер": 4, "четверга": 4, "четвергу": 4,
    "пт": 5, "пят": 5, "п'ят": 5, "пятниц": 5, "п'ятниц": 5, "п'ятниця": 5, "п'ятниці": 5, "п'ятницю": 5,
    "сб": 6, "суб": 6, "субот": 6, "субота": 6, "суботи": 6, "суботу": 6,
    "нд": 7, "нед": 7, "неділ": 7, "неділя": 7, "неділі": 7, "неділю": 7,
}


def _parse_days_of_week_from_text(text: str) -> list[int]:
    """Витягує номери днів тижня з тексту."""
    result = set()
    text_lower = text.lower()
    
    day_patterns = [
        (r"понед[іи]лк[аиу]", 1),
        (r"вівтор[о]?[к]?[аиу]?", 2),
        (r"сер[е]?[д][аиу]?", 3),
        (r"четв[е]?[р][аиу]?", 4),
        (r"п[\'']?ятниц[яиі]", 5),
        (r"суб[о]?[т][аиу]?", 6),
        (r"нед[іи]л[яиі]", 7),
    ]
    
    for pattern, day_num in day_patterns:
        if re.search(pattern, text_lower):
            result.add(day_num)
    
    short_forms = [
        (r"\bпн\b", 1), (r"\bвт\b", 2), (r"\bср\b", 3),
        (r"\bчт\b", 4), (r"\bпт\b", 5), (r"\bсб\b", 6), (r"\bнд\b", 7),
    ]
    
    for pattern, day_num in short_forms:
        if re.search(pattern, text_lower):
            result.add(day_num)
    
    return sorted(result)


def parse_natural_language(text: str) -> dict:
    """
    Парсер природної мови для створення завдань.
    Розпізнає: назву, дату, час, правило повторення.
    """
    original_text = text.strip()
    title = original_text
    category = "personal"
    priority = "normal"
    due_date: Optional[str] = None
    due_at: Optional[str] = None
    recurrence: Optional[dict] = None

    text_lower = text.lower()

    logger.info(f"=== ПОЧАТОК ПАРСИНГУ: '{original_text}' ===")

    # =========================================================================
    # 1. ПРАВИЛО ПОВТОРЕННЯ
    # =========================================================================
    if re.search(r"щодня|щоденно|щоденний", text_lower):
        recurrence = {"rule_type": "daily"}
        logger.info("✅ РОЗПІЗНАНО ПРАВИЛО: daily")
        title = re.sub(r"щодня|щоденно|щоденний", " ", title, flags=re.IGNORECASE)

    # КОЖНІ N ДНІВ (виправлено: додано "і" в клас символів)
    elif re.search(r"кожн[иаі]\s+(\d+)\s+дн[іи]", text_lower):
        match = re.search(r"кожн[иаі]\s+(\d+)\s+дн[іи]", text_lower)
        if match:
            n = int(match.group(1))
            recurrence = {"rule_type": "every_n_days", "interval_days": n}
            logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: every_n_days, n={n}")
            title = re.sub(r"кожн[иаі]\s+\d+\s+дн[іи]", " ", title, flags=re.IGNORECASE)

    # КОЖНІ N ТИЖНІВ (виправлено: додано "і")
    elif re.search(r"кожн[иаі]\s+(\d+)\s+тижн[іи]", text_lower):
        match = re.search(r"кожн[иаі]\s+(\d+)\s+тижн[іи]", text_lower)
        if match:
            n = int(match.group(1))
            recurrence = {"rule_type": "every_n_days", "interval_days": n * 7}
            logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: every_n_days (кожні {n} тижнів = {n*7} днів)")
            title = re.sub(r"кожн[иаі]\s+\d+\s+тижн[іи]", " ", title, flags=re.IGNORECASE)

    # КОЖНІ N МІСЯЦІВ (виправлено: додано "і")
    elif re.search(r"кожн[иаі]\s+(\d+)\s+місяц[іи]", text_lower):
        match = re.search(r"кожн[иаі]\s+(\d+)\s+місяц[іи]", text_lower)
        if match:
            n = int(match.group(1))
            recurrence = {"rule_type": "every_n_months", "interval_months": n}
            logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: every_n_months, n={n}")
            title = re.sub(r"кожн[иаі]\s+\d+\s+місяц[іи]", " ", title, flags=re.IGNORECASE)

    # КОЖНІ N РОКІВ (виправлено: додано "і")
    elif re.search(r"кожн[иаі]\s+(\d+)\s+рок[іи]", text_lower):
        match = re.search(r"кожн[иаі]\s+(\d+)\s+рок[іи]", text_lower)
        if match:
            n = int(match.group(1))
            recurrence = {"rule_type": "yearly", "interval_years": n}
            logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: yearly, n={n}")
            title = re.sub(r"кожн[иаі]\s+\d+\s+рок[іи]", " ", title, flags=re.IGNORECASE)

    elif re.search(r"щотижня|щотижнево|щотижневий", text_lower):
        recurrence = {"rule_type": "weekly"}
        logger.info("✅ РОЗПІЗНАНО ПРАВИЛО: weekly")
        title = re.sub(r"щотижня|щотижнево|щотижневий", " ", title, flags=re.IGNORECASE)

    # ЩОМІСЯЦЯ з числом — обчислюємо найближчу дату
    elif re.search(r"щомісяця|щомісячно|щомісячний", text_lower):
        day_match = re.search(r"(\d{1,2})\s+(?:числа|го|число)", text_lower)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                recurrence = {"rule_type": "monthly", "day_of_month": day}
                logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: monthly, day={day}")
                
                # Обчислюємо найближчу дату з цим числом
                today = datetime.now().date()
                import calendar
                year = today.year
                month = today.month
                
                # Якщо сьогодні вже після цього числа — беремо наступний місяць
                if today.day > day:
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
                
                max_day = calendar.monthrange(year, month)[1]
                actual_day = min(day, max_day)
                due_date = f"{year}-{month:02d}-{actual_day:02d}"
                logger.info(f"Для monthly встановлено початкову дату: {due_date}")
                
                title = re.sub(r"щомісяця|щомісячно|щомісячний", " ", title, flags=re.IGNORECASE)
                title = re.sub(r"\d{1,2}\s+(?:числа|го|число)", " ", title, flags=re.IGNORECASE)
        else:
            recurrence = {"rule_type": "monthly"}
            logger.info("✅ РОЗПІЗНАНО ПРАВИЛО: monthly (той самий день)")
            title = re.sub(r"щомісяця|щомісячно|щомісячний", " ", title, flags=re.IGNORECASE)

    else:
        specific_day_patterns = [
            r"щопонед[іи]лк[аиу]",
            r"щовівтор[о]?[к]?[аиу]?",
            r"щосер[е]?[д][аиу]?",
            r"щочетв[е]?[р][аиу]?",
            r"щоп['']ятниц[яиі]",
            r"щосуб[о]?[т][аиу]?",
            r"щон[е]?[д][іи]л[яиі]",
        ]

        found_specific = False
        for pattern in specific_day_patterns:
            if re.search(pattern, text_lower):
                found_specific = True
                logger.info(f"Знайдено патерн конкретного дня: {pattern}")
                break

        if found_specific:
            days = _parse_days_of_week_from_text(text)
            if days:
                recurrence = {
                    "rule_type": "specific_days",
                    "days_of_week": ",".join(str(d) for d in days),
                }
                logger.info(f"✅ РОЗПІЗНАНО ПРАВИЛО: specific_days, days={days}")
                for pattern in specific_day_patterns:
                    title = re.sub(pattern, " ", title, flags=re.IGNORECASE)
                title = re.sub(r"\bі\b|\bта\b|\bй\b", " ", title, flags=re.IGNORECASE)

    if not recurrence:
        logger.info("❌ ПРАВИЛО ПОВТОРЕННЯ НЕ РОЗПІЗНАНО")

    # =========================================================================
    # 2. ПОШУК ЯВНОЇ ДАТИ (ДД.ММ.РРРР)
    # =========================================================================
    explicit_date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    parsed_date_obj: Optional[datetime] = None
    clean_text_for_time = text

    if explicit_date_match:
        day, month, year = explicit_date_match.groups()
        try:
            parsed_date_obj = datetime(int(year), int(month), int(day))
            logger.info(f"Знайдено явну дату: {parsed_date_obj.date()}")
            clean_text_for_time = text.replace(explicit_date_match.group(0), " ")
        except ValueError as e:
            logger.warning(f"Невалідна дата {day}.{month}.{year}: {e}")

    # =========================================================================
    # 3. ВІДНОСНІ ДАТИ (тільки якщо немає явної дати і немає повторення)
    # =========================================================================
    if parsed_date_obj is None and not recurrence:
        relative_map = [
            (r"післязавтра", 2),
            (r"після\s+завтра", 2),
            (r"завтра", 1),
            (r"сьогодні", 0),
        ]

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for pattern, days_offset in relative_map:
            if re.search(pattern, text_lower):
                parsed_date_obj = today + timedelta(days=days_offset)
                logger.info(f"Знайдено відносну дату: '{pattern}' -> {parsed_date_obj.date()}")
                clean_text_for_time = re.sub(pattern, " ", text_lower)
                break

    # =========================================================================
    # 4. ПОШУК ЧАСУ
    # =========================================================================
    time_match = re.search(
        r"(?:о|об|в)\s+(\d{1,2})[:\.](\d{2})|(\d{1,2})[:\.](\d{2})",
        clean_text_for_time.lower(),
    )

    parsed_hour: Optional[int] = None
    parsed_minute: Optional[int] = None

    if time_match:
        h1, m1, h2, m2 = time_match.groups()
        if h1 is not None:
            parsed_hour = int(h1)
            parsed_minute = int(m1)
        else:
            parsed_hour = int(h2)
            parsed_minute = int(m2)

        if 0 <= parsed_hour <= 23 and 0 <= parsed_minute <= 59:
            logger.info(f"Знайдено час: {parsed_hour:02d}:{parsed_minute:02d}")
        else:
            logger.warning(f"Час невалідний: {parsed_hour}:{parsed_minute}, ігноруємо")
            parsed_hour = None
            parsed_minute = None

    # =========================================================================
    # 5. ФОРМУВАННЯ due_date / due_at
    # =========================================================================
    if parsed_date_obj is not None:
        if parsed_hour is not None and parsed_minute is not None:
            due_datetime = parsed_date_obj.replace(
                hour=parsed_hour, minute=parsed_minute, second=0, microsecond=0
            )
            due_at = due_datetime.isoformat()
            logger.info(f"Встановлено due_at: {due_at}")
        else:
            due_date = parsed_date_obj.date().isoformat()
            logger.info(f"Встановлено due_date: {due_date}")

    # Для повторюваних завдань без явної дати — ставимо сьогодні як базу
    # (крім monthly з day_of_month, який вже обчислений вище)
    if recurrence and not due_date and not due_at:
        if recurrence.get("rule_type") != "monthly" or not recurrence.get("day_of_month"):
            today = datetime.now().date()
            due_date = today.isoformat()
            logger.info(f"Для повторюваного завдання встановлено базову дату: {due_date}")

    # =========================================================================
    # 6. ОЧИЩЕННЯ НАЗВИ
    # =========================================================================
    title = re.sub(r"\d{2}\.\d{2}\.\d{4}", " ", title)
    title = re.sub(r"післязавтра", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"після\s+завтра", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"завтра", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"сьогодні", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"(?:о|об|в)\s+\d{1,2}[:\.]\d{2}", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\d{1,2}[:\.]\d{2}", " ", title)

    title = re.sub(r"[,;:]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .-")

    if not title or len(title) < 2:
        title = original_text
        title = re.sub(r"\d{2}\.\d{2}\.\d{4}", " ", title)
        title = re.sub(r"\d{1,2}[:\.]\d{2}", " ", title)
        title = re.sub(r"[,;:]+", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" .-")

        if not title:
            title = "Нове завдання"

    logger.info("=== РЕЗУЛЬТАТ ПАРСИНГУ ===")
    logger.info(f"  Назва: '{title}'")
    logger.info(f"  due_date: {due_date}")
    logger.info(f"  due_at: {due_at}")
    logger.info(f"  recurrence: {recurrence}")
    logger.info("==========================")

    return {
        "title": title,
        "category": category,
        "priority": priority,
        "due_date": due_date,
        "due_at": due_at,
        "recurrence": recurrence,
    }
