"""
Конфигурация приложения
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Базовые настройки
BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"

# Создаем директорию для сессий если её нет
SESSIONS_DIR.mkdir(exist_ok=True)

# Настройки Flask
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Настройки Telegram API
API_ID = int(os.getenv("API_ID", "0"))  # Получить на https://my.telegram.org
API_HASH = os.getenv("API_HASH", "")    # Получить на https://my.telegram.org

# Время жизни QR-кода в секундах (реальный таймаут Telethon ~60 секунд)
QR_CODE_TIMEOUT = 25

# Порт для Flask (Render использует переменную PORT)
FLASK_PORT = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")

