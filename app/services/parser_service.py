"""Сервіс для парсингу природної мови при створенні завдань."""

import logging
import re
from datetime import datetime, timedelta
from app.utils.dates import today_kyiv
from app.services.recurrence_service import parse_days_of_week

logger = logging.getLogger(__name__)

RELATIVE_DATES = {
    "сьогодні": 0,
    "завтра": 1,
    "післязавтра": 2,
    "наступного тижня": 7,
}

WEEKDAY_PREFIX_PATTERN = (
    r"(?:щопонеділка|щовівторка|щосереди|щочетверга|"
    r"щоп['’ʼ]?ятниці|щоп['’ʼ]?ятниця|щосуботи|щонеділі)"
)


def parse_natural_language(text: str) -> dict:
    """Парсить текст завдання і витягує дату, час, повторення та очищену назву."""
    logger.info(f"=== ПОЧАТОК ПАРСИНГУ: '{text}' ===")

    result = {
        "title": text.strip(),
        "due_date": None,
        "due_at": None,
        "recurrence": None,
        "category": "personal",
        "priority": "normal",
    }

    text_lower = text.lower()
    today = today_kyiv()

    # 1. ПЕРЕВІРКА ПОВТОРЕНЬ
    recurrence_match = None

    # 1a. Конкретне число місяця: "щомісяця 25 числа" або "щомісяця 25-го"
    monthly_day_match = re.search(
        r"щомісяця\s+(\d{1,2})(?:-?го|\s+числа)?", text_lower
    )
    # 1b. Конкретні дні тижня: "щопонеділка і щоп'ятниці"
    weekday_matches = re.findall(WEEKDAY_PREFIX_PATTERN, text_lower)

    if monthly_day_match:
        day_num = int(monthly_day_match.group(1))
        if 1 <= day_num <= 31:
            recurrence_match = {"rule_type": "monthly", "day_of_month": day_num}
            text = re.sub(
                r"щомісяця\s+\d{1,2}(?:-?го|\s+числа)?", "", text, flags=re.IGNORECASE
            )
    elif weekday_matches:
        days = parse_days_of_week(" ".join(weekday_matches))
        if days:
            recurrence_match = {
                "rule_type": "specific_days",
                "days_of_week": ",".join(str(d) for d in days),
            }
            text = re.sub(
                rf"(?:{WEEKDAY_PREFIX_PATTERN}(?:\s*(?:,|і|та)\s*)?)+",
                " ",
                text,
                flags=re.IGNORECASE,
            )
    elif "щодня" in text_lower or "щоденно" in text_lower:
        recurrence_match = {"rule_type": "daily"}
        text = re.sub(r"щодня|щоденно", "", text, flags=re.IGNORECASE)
    elif "щотижня" in text_lower:
        recurrence_match = {"rule_type": "weekly"}
        text = re.sub(r"щотижня", "", text, flags=re.IGNORECASE)
    elif "щомісяця" in text_lower:
        recurrence_match = {"rule_type": "monthly"}
        text = re.sub(r"щомісяця", "", text, flags=re.IGNORECASE)
    elif "щороку" in text_lower or "щорічно" in text_lower:
        recurrence_match = {"rule_type": "yearly"}
        text = re.sub(r"щороку|щорічно", "", text, flags=re.IGNORECASE)
    else:
        every_match = re.search(r"кожні\s+(\d+)\s+(днів|дні|день|тижнів|тижні|місяців|місяці|років|роки)", text_lower)
        if every_match:
            num = int(every_match.group(1))
            unit = every_match.group(2)
            if unit.startswith("д"):
                recurrence_match = {"rule_type": "every_n_days", "interval_days": num}
            elif unit.startswith("тиж"):
                recurrence_match = {"rule_type": "every_n_days", "interval_days": num * 7}
            elif unit.startswith("міс"):
                recurrence_match = {"rule_type": "every_n_months", "interval_months": num}
            elif unit.startswith("рок"):
                recurrence_match = {"rule_type": "yearly", "interval_years": num}
            text = re.sub(
                r"кожні\s+\d+\s+(?:днів|дні|день|тижнів|тижні|місяців|місяці|років|роки)",
                "",
                text,
                flags=re.IGNORECASE,
            )

    if recurrence_match:
        result["recurrence"] = recurrence_match
        logger.info(f"✅ Знайдено правило повторення: {recurrence_match}")

    # 2. ПЕРЕВІРКА АБСОЛЮТНОЇ ДАТИ
    date_match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
    if date_match:
        day, month, year = date_match.groups()
        if len(year) == 2:
            year = "20" + year
        try:
            parsed_date = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y").date()
            result["due_date"] = parsed_date.isoformat()
            logger.info(f"✅ Знайдено абсолютну дату: {result['due_date']}")
            text = text.replace(date_match.group(0), "").strip()
        except ValueError:
            logger.warning("⚠️ Невірний формат абсолютної дати")

    # 3. ПЕРЕВІРКА ВІДНОСНОЇ ДАТИ
    if not result["due_date"]:
        sorted_words = sorted(RELATIVE_DATES.keys(), key=len, reverse=True)
        for word in sorted_words:
            days_offset = RELATIVE_DATES[word]
            if word in text_lower:
                target_date = today + timedelta(days=days_offset)
                result["due_date"] = target_date.isoformat()
                logger.info(f"✅ Знайдено відносну дату: '{word}' -> {result['due_date']}")
                text = re.sub(r"" + re.escape(word) + r"", "", text, flags=re.IGNORECASE).strip()
                break

    # 4. ПЕРЕВІРКА ЧАСУ
    time_match = re.search(r"(?:^|\s)(?:на|о|в|об|около)\s+(\d{1,2}):(\d{2})(?:\s|$)", text, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            base_date = result.get("due_date") or today.isoformat()
            result["due_at"] = f"{base_date}T{hour:02d}:{minute:02d}:00"
            if result.get("recurrence"):
                result["recurrence"]["execution_time"] = f"{hour:02d}:{minute:02d}"
            logger.info(f"✅ Знайдено час: {hour:02d}:{minute:02d}, встановлено due_at: {result['due_at']}")
            text = re.sub(
                r"(?:^|\s)(?:на|о|в|об|около)\s+\d{1,2}:\d{2}(?:\s|$)",
                " ",
                text,
                flags=re.IGNORECASE,
            ).strip()
        else:
            logger.warning(f"⚠️ Невірний час: {hour}:{minute}")

    # 5. ВИЗНАЧЕННЯ КАТЕГОРІЇ ТА ПРІОРИТЕТУ
    if any(word in text_lower for word in ["робота", "офіс", "зустріч", "дзвінок"]):
        result["category"] = "work"
    if any(word in text_lower for word in ["терміново", "важливо", "asap"]):
        result["priority"] = "high"

    # 6. ОЧИЩЕННЯ НАЗВИ
    result["title"] = re.sub(r"\s+", " ", text).strip(" .,;:-")

    if not result["title"]:
        result["title"] = "Нове завдання"

    return result
