import io
import os
from cc_converter import convert_to_pdf
from pathlib import Path
from config import ALLOWED_EXTENSIONS, PRICE
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from r2_storage import R2Client, _human_size, CONTENT_TYPES


BASE_DIR = Path(__file__).parent / "web"


app = FastAPI(title="Copy Center File Viewer")


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


FILE_TYPES = {
    ".pdf": {"icon": "pdf", "color": "#e74c3c"},
    ".doc": {"icon": "word", "color": "#2b579a"},
    ".docx": {"icon": "word", "color": "#2b579a"},
    ".png": {"icon": "image", "color": "#27ae60"},
    ".jpg": {"icon": "image", "color": "#27ae60"},
    ".jpeg": {"icon": "image", "color": "#27ae60"},
}


class FileInfo(BaseModel):
    name: str
    key: str
    size: int
    size_human: str
    type: str
    icon: str
    color: str
    page_count: int | None = None


def get_file_info(key: str, size: int) -> FileInfo:
    name = Path(key).name
    ext = Path(name).suffix.lower()
    file_type = FILE_TYPES.get(ext, {"icon": "file", "color": "#95a5a6"})

    return FileInfo(
        name=name,
        key=key,
        size=size,
        size_human=_human_size(size),
        type=ext.lstrip("."),
        icon=file_type["icon"],
        color=file_type["color"],
    )


async def count_pdf_pages(r2_client: R2Client, key: str) -> int | None:
    import io
    from pypdf import PdfReader

    try:
        data = r2_client.download_bytes(key)
        reader = PdfReader(io.BytesIO(data))

        if reader.is_encrypted:
            if reader.decrypt("") == 0:
                return None

        return len(reader.pages)

    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(name="index.html", request=request)


@app.get("/{telegram_id}", response_class=HTMLResponse)
async def view_files(request: Request, telegram_id: str):
    return templates.TemplateResponse(name="index.html", request=request)


@app.get("/api/files/{telegram_id}")
async def list_files(telegram_id: str):
    try:
        r2_client = R2Client()
        prefix = f"{telegram_id}/"
        objects = r2_client.list_objects(prefix=prefix)

        files = []
        for obj in objects:
            file_info = get_file_info(obj["key"], obj["size"])

            if file_info.type == "pdf":
                file_info.page_count = await count_pdf_pages(r2_client, obj["key"])

            files.append(file_info)

        return {"telegram_id": telegram_id, "files": files, "count": len(files), "price": PRICE}
    except Exception as e:
        print(f"Error listing files for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")


@app.get("/api/preview/{telegram_id}/{filename:path}")
async def get_preview_url(telegram_id: str, filename: str):
    r2_client = R2Client()
    key = f"{telegram_id}/{filename}"

    try:
        r2_client.get_object_info(key)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    url = r2_client.generate_presigned_url(key, expires_in=3600)
    return {"url": url}


@app.delete("/api/files/{telegram_id}/{filename:path}")
async def delete_file(telegram_id: str, filename: str):
    try:
        r2_client = R2Client()
        key = f"{telegram_id}/{filename}"
        r2_client.get_object_info(key)
        r2_client.delete_object(key)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {e}")


@app.post("/api/upload/{telegram_id}")
async def upload_files(telegram_id: str, files: list[UploadFile] = File(...)):
    try:
        r2_client = R2Client()
        uploaded = []
        for f in files:
            ext = Path(f.filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Недопустимый формат: {ext}")
            file_bytes = await f.read()
            object_key = f"{telegram_id}/{f.filename}"

            if ext == ".doc" or ext == ".docx":
                pdf_bytes = convert_to_pdf(file_bytes, f.filename)
                file_bytes = pdf_bytes
                ext = ".pdf"
                pdf_filename = os.path.splitext(f.filename)[0] + ".pdf"
                object_key = f"{telegram_id}/{pdf_filename}"

            content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
            r2_client.upload_bytes(file_bytes, object_key=object_key, content_type=content_type)
            uploaded.append(object_key)
        return {"status": "ok", "count": len(uploaded)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


"""
async def handle_document(message: Message):
    # Скачиваем из Telegram в память
    file_bytes = await download_file_to_bytes(message)
    filename = message.document.file_name

    if filename.endswith((".doc", ".docx")):
        pdf_bytes = convert_to_pdf(file_bytes, filename)
        
        # Загружаем PDF обратно в R2
        pdf_filename = filename.rsplit(".", 1)[0] + ".pdf"
        upload_to_r2(pdf_bytes, f"{user_id}/{pdf_filename}")
"""
