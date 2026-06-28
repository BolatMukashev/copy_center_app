import logging
import os
from r2_storage import upload_to_r2, CONTENT_TYPES
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from config import BOT_API_KEY, ADMIN_ID, SITE, ALLOWED_EXTENSIONS
from cc_converter import convert_to_pdf, convert_to_png


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


bot = Bot(token=BOT_API_KEY)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def download_from_telegram(file_id: str) -> bytes:
    """Скачивает файл из Telegram по file_id, возвращает байты."""
    file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(file.file_path)
    return file_bytes.read()


async def handle_file(message: types.Message, file_id: str, file_name: str) -> None:
    """Валидирует, скачивает из TG и загружает в R2."""
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

    await message.answer("⏳ Добавляю файл в очередь...")

    file_bytes = await download_from_telegram(file_id)

    if ext == ".doc" or ext == ".docx" or ext == ".pptx":
        await message.answer("⏳ Конвертирую в PDF...")
        pdf_bytes = convert_to_pdf(file_bytes, file_name)
        file_bytes = pdf_bytes
        ext = ".pdf"
        pdf_filename = os.path.splitext(file_name)[0] + ".pdf"
        file_name = pdf_filename
        object_key = f"{user_id}/{file_name}"
    
    if ext == ".heic" or ext == ".heif" or ext == ".tiff" or ext == ".tif" or ext == ".webp":
        await message.answer("⏳ Конвертирую в PNG...")
        png_bytes = convert_to_png(file_bytes, file_name)
        file_bytes = png_bytes
        ext = ".png"
        png_filename = os.path.splitext(file_name)[0] + ".png"
        file_name = png_filename
        object_key = f"{user_id}/{file_name}"

    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
    upload_to_r2(file_bytes, object_key=object_key, content_type=content_type)

    logger.info(f"Файл от пользователя {user_id} сохранён: {object_key}")
    await message.answer(
        f"✅ Файл «{file_name}» добавлен в очередь!\n"
        f'Путь: <a href="{SITE}/{user_id}">"{SITE}/{user_id}"</a>',
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    await message.answer(
        f"Привет, {user_name}! Я бот. Твой ID: {user_id}\n"
        f"Отправь мне файл или изображение"
    )


@dp.message(F.document)
async def handle_document(message: types.Message):
    document = message.document
    file_name = document.file_name or "unknown"
    await handle_file(message, document.file_id, file_name)


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    file_name = f"{photo.file_unique_id}.jpg"
    await handle_file(message, photo.file_id, file_name)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())