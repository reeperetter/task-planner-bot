import logging
from typing import Optional
from app.repositories import user_repository, settings_repository
from app.config import config

logger = logging.getLogger(__name__)

async def register_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> dict:
    """
    Зареєструвати користувача або отримати існуючого.
    Перевіряє режим доступу (open/allowlist).
    """
    # Перевірка режиму доступу
    if config.ACCESS_MODE == "allowlist":
        # Тут можна додати перевірку списку дозволених користувачів
        # Для першої версії просто блокуємо всіх, окрім тих, хто вже зареєстрований
        existing_user = await user_repository.get_user_by_telegram_id(telegram_id)
        if not existing_user:
            logger.warning(f"Спроба доступу від неавторизованого користувача: telegram_id={telegram_id}")
            return {"status": "denied", "message": "Доступ заборонено. Зверніться до адміністратора."}
        return {"status": "exists", "user": existing_user}
    
    # Режим open: реєструємо всіх
    existing_user = await user_repository.get_user_by_telegram_id(telegram_id)
    
    if existing_user:
        logger.info(f"Користувач вже існує: telegram_id={telegram_id}")
        return {"status": "exists", "user": existing_user}
    
    # Створюємо нового користувача
    user_id = await user_repository.create_user(telegram_id, username, first_name)
    
    # Створюємо стандартні налаштування
    await settings_repository.create_user_settings(user_id)
    
    # Отримуємо повну інформацію про користувача
    user = await user_repository.get_user_by_telegram_id(telegram_id)
    
    logger.info(f"Зареєстровано нового користувача: telegram_id={telegram_id}, user_id={user_id}")
    return {"status": "created", "user": user}
