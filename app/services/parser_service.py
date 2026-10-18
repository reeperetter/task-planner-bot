import re
from datetime import datetime

def parse_natural_language(text: str) -> dict:
    """
    Базовий парсер природної мови для створення завдань.
    Намагається визначити категорію, пріоритет та дату з тексту.
    """
    title = text.strip()
    category = "personal"
    priority = "normal"
    due_date = None

    text_lower = text.lower()

    # 1. Визначення категорії
    if any(word in text_lower for word in ["робот", "робоч", "служб"]):
        category = "work"

    # 2. Визначення пріоритету
    if any(word in text_lower for word in ["висок", "термін", "термінов", "важлив", "терново"]):
        priority = "high"
    elif any(word in text_lower for word in ["низьк", "неважлив", "потім"]):
        priority = "low"

    # 3. Визначення дати (шукаємо формат ДД.ММ.РРРР)
    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    if date_match:
        try:
            # Парсимо дату та конвертуємо в ISO формат
            parsed_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
            due_date = parsed_date.strftime("%Y-%m-%d")  # <-- Конвертуємо в ISO формат!
            # Прибираємо дату з назви, щоб не дублювалася
            title = title.replace(date_match.group(1), "").strip()
        except ValueError:
            pass

    # 4. Очищення назви від зайвих розділових знаків на кінці
    title = title.strip(",. ")

    # Якщо після очищення назва порожня, ставимо дефолтну
    if not title:
        title = "Нове завдання"

    return {
        "title": title,
        "category": category,
        "priority": priority,
        "due_date": due_date
    }
