"""Сервіс для парсингу природної мови при створенні завдань."""

import logging
import re
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# Словник для відносних дат
RELATIVE_DATES = {
    "сьогодні": 0,
    "завтра": 1,
    "післязавтра": 2,
    "наступного тижня": 7,
}

# Словник днів тижня для повторень
WEEKDAYS_RU = {
    "понеділок": 1, "пн": 1,
    "вівторок": 2, "вт": 2,
    "середа": 3, "ср": 3,
    "четвер": 4, "чт": 4,
    "п'ятниця": 5, "пт": 5,
    "субота": 6, "сб": 6,
    "неділя": 7, "нд": 7,
}

def parse_natural_language(text: str) -> dict:
    """
    Парсить текст завдання і витягує дату, час, повторення та очищену назву.
    """
    logger.info(f"=== ПОЧАТОК ПАРСИНГУ: '{text}' ===")
    
    result = {
        "title": text.strip(),
        "due_date": None,
        "due_at": None,
        "recurrence": None,
        "category": "personal",
        "priority": "normal",
    }

    original_text = text
    text_lower = text.lower()

    # 1. ПЕРЕВІРКА ПОВТОРЕНЬ (найбільш специфічні маркери)
    recurrence_match = None
    if "щодня" in text_lower or "щоденно" in text_lower:
        recurrence_match = {"rule_type": "daily"}
    elif "щотижня" in text_lower:
        recurrence_match = {"rule_type": "weekly"}
    elif "щомісяця" in text_lower:
        recurrence_match = {"rule_type": "monthly"}
    elif "щороку" in text_lower or "щорічно" in text_lower:
        recurrence_match = {"rule_type": "yearly"}
    else:
        # Перевірка "кожні N днів/тижнів/місяців"
        every_match = re.search(r'кожні\s+(\d+)\s+(днів|тижнів|місяців|років)', text_lower)
        if every_match:
            num = int(every_match.group(1))
            unit = every_match.group(2)
            if "днів" in unit:
                recurrence_match = {"rule_type": "every_n_days", "interval_days": num}
            elif "тижнів" in unit:
                recurrence_match = {"rule_type": "every_n_days", "interval_days": num * 7}
            elif "місяців" in unit:
                recurrence_match = {"rule_type": "every_n_months", "interval_months": num}
            elif "років" in unit:
                recurrence_match = {"rule_type": "every_n_months", "interval_months": num * 12}

    if recurrence_match:
        result["recurrence"] = recurrence_match
        logger.info(f"✅ Знайдено правило повторення: {recurrence_match}")
        # Видаляємо маркер повторення з назви
        text = re.sub(r'кожні\s+\d+\s+(?:днів|тижнів|місяців|років)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'щодня|щоденно|щотижня|щомісяця|щороку|щорічно', '', text, flags=re.IGNORECASE)

    # 2. ПЕРЕВІРКА АБСОЛЮТНОЇ ДАТИ (ДД.ММ.РРРР або ДД/ММ/РРРР)
    date_match = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})', text)
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

    # 3. ПЕРЕВІРКА ВІДНОСНОЇ ДАТИ (сьогодні, завтра), якщо абсолютна не знайдена
    if not result["due_date"]:
        for word, days_offset in RELATIVE_DATES.items():
            if word in text_lower:
                target_date = date.today() + timedelta(days=days_offset)
                result["due_date"] = target_date.isoformat()
                logger.info(f"✅ Знайдено відносну дату: '{word}' -> {result['due_date']}")
                text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE).strip()
                break

    # 4. ПЕРЕВІРКА ЧАСУ (наприклад, "на 12:20", "о 10:00", "в 15:30")
    time_match = re.search(r'(?:на|о|в|об|около|о\s+)\s*(\d{1,2}):(\d{2})\b', text, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            base_date = result.get("due_date") or date.today().isoformat()
            result["due_at"] = f"{base_date}T{hour:02d}:{minute:02d}:00"
            logger.info(f"✅ Знайдено час: {hour:02d}:{minute:02d}, встановлено due_at: {result['due_at']}")
            
            # Видаляємо час І прийменник перед ним з тексту назви
            text = re.sub(r'(?:на|о|в|об|около|о\s+)\s*\d{1,2}:\d{2}\b', '', text, flags=re.IGNORECASE).strip()
        else:
            logger.warning(f"⚠️ Невірний час: {hour}:{minute}")

    # 5. ВИЗНАЧЕННЯ КАТЕГОРІЇ ТА ПРИОРИТЕТУ ЗА КЛЮЧОВИМИ СЛОВАМИ (опціонально)
    if any(word in text_lower for word in ["робота", "офіс", "зустріч", "дзвінок"]):
        result["category"] = "work"
    if any(word in text_lower for word in ["терміново", "важливо", " ASAP"]):
        result["priority"] = "high"

    # 6. ОЧИЩЕННЯ НАЗВИ від зайвих пробілів та розділових знаків на кінці
    result["title"] = re.sub(r'\s+', ' ', text).strip(" .,;:-")
    
    # Якщо назва стала порожньою, повертаємо дефолт
    if not result["title"]:
        result["title"] = "Нове завдання"

    logger.info("=== РЕЗУЛЬТАТ ПАРСИНГУ ===")
    logger.info(f"  Назва: '{result['title']}'")
    logger.info(f"  due_date: {result['due_date']}")
    logger.info(f"  due_at: {result['due_at']}")
    logger.info(f"  recurrence: {result['recurrence']}")
    logger.info("==========================")

    return result
