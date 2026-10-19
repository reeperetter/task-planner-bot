"""Парсер природної мови для створення завдань."""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Маппінг назв днів тижня українською -> ISO номер (1=Пн, 7=Нд)
WEEKDAY_MAP = {
    "пн": 1, "пон": 1, "понед": 1, "понеділок": 1,
    "вт": 2, "вів": 2, "вівтор": 2, "вівторок": 2,
    "ср": 3, "сер": 3, "серед": 3, "середа": 3,
    "чт": 4, "чет": 4, "четвер": 4,
    "пт": 5, "пят": 5, "п'ят": 5, "пятниц": 5, "п'ятниц": 5,
    "сб": 6, "суб": 6, "субот": 6, "субота": 6,
    "нд": 7, "нед": 7, "неділ": 7, "неділя": 7,
}


def _parse_days_of_week_from_text(text: str) -> list[int]:
    """Витягує номери днів тижня з тексту."""
    result = set()
    text_lower = text.lower()
    for key, value in WEEKDAY_MAP.items():
        if key in text_lower:
            result.add(value)
    return sorted(result)


def parse_natural_language(text: str) -> dict:
    """
    Парсер природної мови для створення завдань.
    Розпізнає: назву, дату, час, категорію, пріоритет, правило повторення.
    """
    original_text = text.strip()
    title = original_text
    category = "personal"
    priority = "normal"
    due_date: Optional[str] = None
    due_at: Optional[str] = None
    recurrence: Optional[dict] = None

    text_lower = text.lower()

    logger.info(f"=== Початок парсингу: '{original_text}' ===")

    # =========================================================================
    # 1. ПРАВИЛО ПОВТОРЕННЯ (перевіряємо ПЕРШИМ, бо впливає на дату)
    # =========================================================================
    # Щодня
    if re.search(r'\bщоден[ннийа]\b', text_lower):
        recurrence = {"rule_type": "daily"}
        logger.info("Правило: щодня")
        title = re.sub(r'\bщоден[ннийа]\b', ' ', title, flags=re.IGNORECASE)

    # Кожні N днів
    elif re.search(r'\bкожн[иа]\s+(\d+)\s+дн[іи]', text_lower):
        match = re.search(r'\bкожн[иа]\s+(\d+)\s+дн[іи]', text_lower)
        if match:
            n = int(match.group(1))
            recurrence = {"rule_type": "every_n_days", "interval_days": n}
            logger.info(f"Правило: кожні {n} днів")
            title = re.sub(r'\bкожн[иа]\s+\d+\s+дн[іи]', ' ', title, flags=re.IGNORECASE)

    # Щотижня
    elif re.search(r'\bщотижн[еєаий]\b', text_lower):
        recurrence = {"rule_type": "weekly"}
        logger.info("Правило: щотижня")
        title = re.sub(r'\bщотижн[еєаий]\b', ' ', title, flags=re.IGNORECASE)

    # У вибрані дні тижня (щопонеділка, щовівторка, або "по понеділках і п'ятницях")
    elif re.search(r'\bщоп[нвечфп]\b|\bпо\s+\w+\s+та?\s+\w+\b', text_lower):
        days = _parse_days_of_week_from_text(text)
        if days:
            recurrence = {
                "rule_type": "specific_days",
                "days_of_week": ",".join(str(d) for d in days),
            }
            logger.info(f"Правило: у дні {days}")
            # Видаляємо назви днів тижня з назви
            for key in WEEKDAY_MAP.keys():
                title = re.sub(rf'\b{key}\b', ' ', title, flags=re.IGNORECASE)
            title = re.sub(r'\bщоп[нвечфп]\b', ' ', title, flags=re.IGNORECASE)
            title = re.sub(r'\bпо\b', ' ', title, flags=re.IGNORECASE)
            title = re.sub(r'\bта?\b', ' ', title, flags=re.IGNORECASE)

    # Щомісяця
    elif re.search(r'\bщомісячн[оаий]|\bщомісяця\b', text_lower):
        # Шукаємо число місяця
        day_match = re.search(r'\b(\d{1,2})\s+(?:числа|го|число)\b', text_lower)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                recurrence = {"rule_type": "monthly", "day_of_month": day}
                logger.info(f"Правило: щомісяця {day}-го")
                title = re.sub(r'\bщомісячн[оаий]|\bщомісяця\b', ' ', title, flags=re.IGNORECASE)
                title = re.sub(r'\b\d{1,2}\s+(?:числа|го|число)\b', ' ', title, flags=re.IGNORECASE)
        else:
            recurrence = {"rule_type": "monthly"}
            logger.info("Правило: щомісяця (той самий день)")
            title = re.sub(r'\bщомісячн[оаий]|\bщомісяця\b', ' ', title, flags=re.IGNORECASE)

    # =========================================================================
    # 2. КАТЕГОРІЯ
    # =========================================================================
    if any(word in text_lower for word in ["робот", "робоч", "служб", "офіс"]):
        category = "work"
        logger.info("Категорія: work")

    # =========================================================================
    # 3. ПРІОРИТЕТ
    # =========================================================================
    if any(word in text_lower for word in ["висок", "термінов", "важлив", "критичн"]):
        priority = "high"
        logger.info("Пріоритет: high")
    elif any(word in text_lower for word in ["низьк", "неважлив"]):
        priority = "low"
        logger.info("Пріоритет: low")

    # =========================================================================
    # 4. ПОШУК ЯВНОЇ ДАТИ (ДД.ММ.РРРР)
    # =========================================================================
    explicit_date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
    parsed_date_obj: Optional[datetime] = None
    clean_text_for_time = text

    if explicit_date_match:
        day, month, year = explicit_date_match.groups()
        try:
            parsed_date_obj = datetime(int(year), int(month), int(day))
            logger.info(f"Знайдено явну дату: {parsed_date_obj.date()}")
            clean_text_for_time = text.replace(explicit_date_match.group(0), ' ')
        except ValueError as e:
            logger.warning(f"Невалідна дата {day}.{month}.{year}: {e}")

    # =========================================================================
    # 5. ЯКЩО ЯВНОЇ ДАТИ НЕМАЄ — ШУКАЄМО ВІДНОСНІ ДАТИ
    # =========================================================================
    if parsed_date_obj is None and not recurrence:
        relative_map = [
            (r'\bпіслязавтра\b', 2),
            (r'\bпісля\s+завтра\b', 2),
            (r'\bзавтра\b', 1),
            (r'\bсьогодні\b', 0),
        ]

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for pattern, days_offset in relative_map:
            if re.search(pattern, text_lower):
                parsed_date_obj = today + timedelta(days=days_offset)
                logger.info(f"Знайдено відносну дату: '{pattern}' -> {parsed_date_obj.date()}")
                clean_text_for_time = re.sub(pattern, ' ', text_lower)
                break

    # =========================================================================
    # 6. ПОШУК ЧАСУ (HH:MM або H:MM)
    # =========================================================================
    time_match = re.search(
        r'(?:о|об|в)\s+(\d{1,2})[:\.](\d{2})|(\d{1,2})[:\.](\d{2})',
        clean_text_for_time.lower()
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
    # 7. ФОРМУВАННЯ due_date / due_at
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
    if recurrence and not due_date and not due_at:
        today = datetime.now().date()
        due_date = today.isoformat()
        logger.info(f"Для повторюваного завдання встановлено базову дату: {due_date}")

    # =========================================================================
    # 8. ОЧИЩЕННЯ НАЗВИ
    # =========================================================================
    title = re.sub(r'\d{2}\.\d{2}\.\d{4}', ' ', title)
    title = re.sub(r'\bпіслязавтра\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\bпісля\s+завтра\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\bзавтра\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\bсьогодні\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'(?:о|об|в)\s+\d{1,2}[:\.]\d{2}', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\b\d{1,2}[:\.]\d{2}\b', ' ', title)

    # Прибираємо ключові слова категорії та пріоритету
    title = re.sub(r'\b(?:робот[аиу]|робоч[аеиі]|служб[аиу]|офіс)\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\b(?:висок[ийаогому]*|термінов[ийаогому]*|важлив[ийаогому]*|критичн[ийаогому]*)\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\b(?:низьк[ийаогому]*|неважлив[ийаогому]*)\b', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\bпріоритет\b', ' ', title, flags=re.IGNORECASE)

    # Прибираємо зайві розділові знаки
    title = re.sub(r'[,;:]+', ' ', title)

    # Нормалізація пробілів
    title = re.sub(r'\s+', ' ', title).strip(' .-')

    # Якщо назва порожня — беремо перші слова оригіналу
    if not title or len(title) < 2:
        words = original_text.split()
        clean_words = []
        for w in words:
            if re.match(r'^\d{2}\.\d{2}\.\d{4}$', w):
                continue
            if re.match(r'^\d{1,2}[:\.]\d{2}$', w):
                continue
            if w.lower() in ('о', 'об', 'в', 'завтра', 'сьогодні', 'післязавтра', 'після', 'робота', 'роботу', 'високий', 'низький'):
                continue
            clean_word = re.sub(r'[,;:]+', '', w).strip()
            if clean_word:
                clean_words.append(clean_word)
            if len(clean_words) >= 5:
                break
        title = ' '.join(clean_words).strip(' .-')

        if not title:
            title = "Нове завдання"

    logger.info(f"=== Результат парсингу ===")
    logger.info(f"  Назва: '{title}'")
    logger.info(f"  Категорія: {category}")
    logger.info(f"  Пріоритет: {priority}")
    logger.info(f"  due_date: {due_date}")
    logger.info(f"  due_at: {due_at}")
    logger.info(f"  Повторення: {recurrence}")
    logger.info(f"==========================")

    return {
        "title": title,
        "category": category,
        "priority": priority,
        "due_date": due_date,
        "due_at": due_at,
        "recurrence": recurrence,
    }
