import io
import os
import requests
import cloudconvert
from config import CC_TOKEN


cloudconvert.configure(api_key=CC_TOKEN, sandbox=False)


def convert_to_pdf(file_bytes: bytes, filename: str) -> bytes:
    # Создаём job с тремя задачами: загрузка → конвертация → экспорт
    job = cloudconvert.Job.create(payload={
        "tasks": {
            "upload-file": {
                "operation": "import/upload"
            },
            "convert-file": {
                "operation": "convert",
                "input": "upload-file",
                "output_format": "pdf",
                "input_format": filename.rsplit(".", 1)[-1].lower()
            },
            "export-file": {
                "operation": "export/url",
                "input": "convert-file"
            }
        }
    })

    # Находим задачу загрузки
    upload_task = next(t for t in job["tasks"] if t["name"] == "upload-file")

    # Загружаем через requests напрямую
    upload_url = upload_task["result"]["form"]["url"]
    upload_params = upload_task["result"]["form"]["parameters"]

    requests.post(
        upload_url,
        data=upload_params,
        files={"file": (filename, io.BytesIO(file_bytes))}
    )

    # Ждём завершения job
    job = cloudconvert.Job.wait(id=job["id"])

    # Находим задачу экспорта
    export_task = next(t for t in job["tasks"] if t["name"] == "export-file")

    if export_task["status"] != "finished":
        raise RuntimeError(f"Конвертация не удалась: {export_task.get('message')}")

    # Скачиваем PDF
    file_url = export_task["result"]["files"][0]["url"]
    response = requests.get(file_url)
    response.raise_for_status()

    return response.content


def convert_to_png(file_bytes: bytes, filename: str) -> bytes:
    # Создаём job с тремя задачами: загрузка → конвертация → экспорт
    job = cloudconvert.Job.create(payload={
        "tasks": {
            "upload-file": {
                "operation": "import/upload"
            },
            "convert-file": {
                "operation": "convert",
                "input": "upload-file",
                "output_format": "png",
                "input_format": filename.rsplit(".", 1)[-1].lower()
            },
            "export-file": {
                "operation": "export/url",
                "input": "convert-file"
            }
        }
    })

    # Находим задачу загрузки
    upload_task = next(t for t in job["tasks"] if t["name"] == "upload-file")

    # Загружаем через requests напрямую
    upload_url = upload_task["result"]["form"]["url"]
    upload_params = upload_task["result"]["form"]["parameters"]

    requests.post(
        upload_url,
        data=upload_params,
        files={"file": (filename, io.BytesIO(file_bytes))}
    )

    # Ждём завершения job
    job = cloudconvert.Job.wait(id=job["id"])

    # Находим задачу экспорта
    export_task = next(t for t in job["tasks"] if t["name"] == "export-file")

    if export_task["status"] != "finished":
        raise RuntimeError(f"Конвертация не удалась: {export_task.get('message')}")

    # Скачиваем PNG
    file_url = export_task["result"]["files"][0]["url"]
    response = requests.get(file_url)
    response.raise_for_status()

    return response.content


if __name__ == "__main__":
    # Использование
    input_filename = "test.docx"

    with open(f"uploads/{input_filename}", "rb") as f:
        docx_bytes = f.read()

    pdf_bytes = convert_to_pdf(docx_bytes, input_filename)

    pdf_filename = os.path.splitext(input_filename)[0] + ".pdf"
    with open(f"uploads/{pdf_filename}", "wb") as f:
        f.write(pdf_bytes)

    print(f"Готово: {pdf_filename}")

    