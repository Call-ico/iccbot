import os

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'  # Используем SQLite для простоты, заменяй на свою БД
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here')
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'your_telegram_bot_token_here')
