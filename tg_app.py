import logging
import os
from r2_storage import R2Client
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_API_KEY, ADMIN_ID

# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# настройка бота
bot = Bot(token=BOT_API_KEY)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Разрешённые расширения
ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}

CONTENT_TYPES = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
}

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    await message.answer(
        f"Привет, {user_name}! Я бот. Твой ID: {user_id}\n"
        f"Отправь мне файл .doc, .docx, .pdf, .png, .jpg или .jpeg — я его сохраню."
    )

async def upload_to_r2(message: types.Message, file_id: str, file_name: str):
    """Скачивает файл по file_id и загружает в R2."""
    _, ext = os.path.splitext(file_name.lower())

    if ext not in ALLOWED_EXTENSIONS:
        await message.answer(
            f"❌ Формат «{ext}» не поддерживается.\n"
            f"Принимаю только: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        return

    assert message.from_user is not None
    user_id = message.from_user.id
    object_key = f"{user_id}/{file_name}"

    await message.answer("⏳ Загружаю файл в облако...")

    file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(file.file_path)
    data = file_bytes.read()

    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    r2 = R2Client()
    r2.upload_bytes(data, object_key=object_key, content_type=content_type)

    logger.info(f"Файл загружен в R2: {object_key} (от пользователя {user_id})")
    await message.answer(
        f"✅ Файл «{file_name}» сохранён в облаке!\n"
        f"Путь: {object_key}"
    )

@dp.message(F.document)
async def handle_document(message: types.Message):
    document = message.document
    file_name = document.file_name or "unknown"
    await upload_to_r2(message, document.file_id, file_name)

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    # Telegram сжимает фото — берём наибольшее разрешение
    photo = message.photo[-1]
    file_name = f"{photo.file_unique_id}.jpg"
    await upload_to_r2(message, photo.file_id, file_name)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())