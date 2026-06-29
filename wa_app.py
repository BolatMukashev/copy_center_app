import logging
import os
import aiohttp
from r2_storage import upload_to_r2, CONTENT_TYPES
from config import GREEN_API_URL, GREEN_API_INSTANCE_ID, GREEN_API_TOKEN, SITE, ALLOWED_EXTENSIONS
from cc_converter import convert_to_pdf, convert_to_png
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import ssl
import certifi

print(f"TOKEN: '{GREEN_API_TOKEN}'")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(title="WhatsApp Copy Center Bot")


def green_api_headers() -> dict:
    return {"Authorization": f"Bearer {GREEN_API_TOKEN}"}


# Создай один раз глобально
ssl_context = ssl.create_default_context(cafile=certifi.where())


async def green_api_send_message(chat_id: str, message: str) -> None:
    url = f"{GREEN_API_URL}/waInstance{GREEN_API_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}"
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            url,
            json={"chatId": chat_id, "message": message},
            headers={"Content-Type": "application/json"}
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"green-api sendMessage error {resp.status}: {text}")
            else:
                logger.info(f"Сообщение отправлено в {chat_id}")


async def download_file(file_url: str) -> bytes:
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(file_url) as resp:
            resp.raise_for_status()
            return await resp.read()


async def handle_file(chat_id: str, file_name: str, file_url: str) -> None:
    _, ext = os.path.splitext(file_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        await green_api_send_message(
            chat_id,
            f"Формат «{ext}» не поддерживается.\n"
            f"Принимаю только: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        return

    await green_api_send_message(chat_id, "Добавляю файл в очередь...")

    file_bytes = await download_file(file_url)
    original_name = file_name

    if ext in (".doc", ".docx", ".pptx"):
        await green_api_send_message(chat_id, "Конвертирую в PDF...")
        file_bytes = convert_to_pdf(file_bytes, file_name)
        ext = ".pdf"
        file_name = os.path.splitext(file_name)[0] + ".pdf"

    if ext in (".heic", ".heif", ".tiff", ".tif", ".webp"):
        await green_api_send_message(chat_id, "Конвертирую в PNG...")
        file_bytes = convert_to_png(file_bytes, file_name)
        ext = ".png"
        file_name = os.path.splitext(file_name)[0] + ".png"

    phone = chat_id.split("@")[0] if "@" in chat_id else chat_id
    object_key = f"{phone}/{file_name}"
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
    upload_to_r2(file_bytes, object_key=object_key, content_type=content_type)

    logger.info(f"Файл от {phone} сохранён: {object_key}")
    await green_api_send_message(
        chat_id,
        f"Файл «{file_name}» добавлен в очередь!\n"
        f"Путь: {SITE}/{phone}"
    )


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    logger.info(f"WEBHOOK BODY: {body}")

    notification_type = body.get("typeWebhook")

    if notification_type == "incomingMessageReceived":
        message_data = body.get("messageData", {})
        chat_id = body.get("senderData", {}).get("chatId", "")
        message_type = message_data.get("typeMessage")

        # Файловые данные лежат в fileMessageData, а не напрямую
        file_data = message_data.get("fileMessageData", {})

        if message_type == "documentMessage":
            file_name = file_data.get("fileName", "unknown")
            file_url = file_data.get("downloadUrl")  # downloadUrl, не fileUrl!
            if file_url:
                await handle_file(chat_id, file_name, file_url)

        elif message_type == "imageMessage":
            file_url = file_data.get("downloadUrl")
            if file_url:
                file_name = file_data.get("fileName") or f"photo_{body.get('timestamp', '')}.jpg"
                await handle_file(chat_id, file_name, file_url)

        elif message_type in ("extendedTextMessage", "textMessage"):
            text = message_data.get("textMessageData", {}).get("textMessage", "")
            await green_api_send_message(
                    chat_id,
                    "Привет! Отправь мне файл или изображение, и я загружу его в очередь на печать."
                )

    return JSONResponse(content={"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
