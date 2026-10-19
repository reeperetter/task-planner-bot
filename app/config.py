import os
from pathlib import Path
from dotenv import load_dotenv

# Завантажуємо .env з кореня проєкту
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class Config:
    # Шукаємо токен під обома іменами для 100% сумісності
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/planner.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ACCESS_MODE: str = os.getenv("ACCESS_MODE", "open")

    def __init__(self):
        # Перевірка обов'язкових змінних (працює при створенні об'єкта)
        if not self.BOT_TOKEN or self.BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
            raise ValueError(
                "❌ TELEGRAM_BOT_TOKEN (або BOT_TOKEN) не встановлено! "
                "Перевірте файл .env або змінні оточення на хостингу."
            )
        
        # Створюємо директорію для БД, якщо її немає
        db_dir = Path(self.DATABASE_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)

# Ініціалізуємо конфігурацію
config = Config()
