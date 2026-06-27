from dotenv import dotenv_values
from pathlib import Path
import os

_env_path = str(Path(__file__).parent / ".env")
config = dotenv_values(_env_path)

# конфиг бота
BOT_API_KEY = os.environ.get("BOT_API_KEY") or config.get("BOT_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID") or config.get("ADMIN_ID")
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)


ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}


"""
Конфиг r2 storage
Настройка переменных окружения (или передать напрямую):
    R2_ACCOUNT_ID       — ID аккаунта Cloudflare
    R2_ACCESS_KEY_ID    — Access Key ID из R2 API Tokens
    R2_SECRET_ACCESS_KEY — Secret Access Key из R2 API Tokens
    R2_BUCKET_NAME      — Имя бакета по умолчанию
"""

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID") or config.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID") or config.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or config.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or config.get("R2_BUCKET_NAME")

CC_TOKEN = os.environ.get("CC_TOKEN") or config.get("CC_TOKEN")

SITE = "http://localhost:8000"
