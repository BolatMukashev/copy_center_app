"""
Cloudflare R2 Object Storage Client
Использует boto3 (S3-совместимый API)

Установка зависимостей:
    pip install boto3

"""

import os
import sys
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError


from config import R2_ACCESS_KEY_ID, R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_SECRET_ACCESS_KEY


class R2Client:
    """Клиент для работы с Cloudflare R2 Object Storage."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.account_id = R2_ACCOUNT_ID or os.environ["R2_ACCOUNT_ID"]
        self.bucket_name = R2_BUCKET_NAME or os.environ.get("R2_BUCKET_NAME")

        endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=R2_ACCESS_KEY_ID or os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=R2_SECRET_ACCESS_KEY or os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    # ──────────────────────────────────────────
    # ЗАГРУЗКА ФАЙЛОВ
    # ──────────────────────────────────────────

    def upload_file(
        self,
        local_path: str,
        object_key: Optional[str] = None,
        bucket: Optional[str] = None,
        content_type: Optional[str] = None,
        extra_args: Optional[dict] = None,
    ) -> str:
        """
        Загрузить файл в R2.

        Args:
            local_path:   Путь к локальному файлу.
            object_key:   Ключ объекта в бакете. По умолчанию — имя файла.
            bucket:       Имя бакета. По умолчанию — self.bucket_name.
            content_type: MIME-тип (например 'image/png').
            extra_args:   Дополнительные параметры boto3 ExtraArgs.

        Returns:
            Ключ загруженного объекта.
        """
        bucket = bucket or self._require_bucket()
        object_key = object_key or Path(local_path).name

        args: dict = {}
        if content_type:
            args["ContentType"] = content_type
        if extra_args:
            args.update(extra_args)

        print(f"⬆  Загрузка: {local_path} → s3://{bucket}/{object_key}")
        self.s3.upload_file(local_path, bucket, object_key, ExtraArgs=args or None)
        print(f"✓  Загружено: {object_key}")
        return object_key

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        bucket: Optional[str] = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Загрузить данные из памяти (bytes) без создания файла."""
        bucket = bucket or self._require_bucket()

        print(f"⬆  Загрузка bytes → s3://{bucket}/{object_key}")
        self.s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        print(f"✓  Загружено: {object_key}")
        return object_key

    # ──────────────────────────────────────────
    # ПРОСМОТР ФАЙЛОВ
    # ──────────────────────────────────────────

    def list_objects(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        max_keys: int = 1000,
    ) -> list[dict]:
        """
        Получить список объектов в бакете.

        Args:
            prefix:   Фильтр по префиксу пути (например 'images/').
            bucket:   Имя бакета.
            max_keys: Максимальное количество объектов.

        Returns:
            Список словарей с полями: key, size, last_modified, etag.
        """
        bucket = bucket or self._require_bucket()

        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=bucket,
            Prefix=prefix,
            PaginationConfig={"MaxItems": max_keys},
        )

        objects = []
        for page in pages:
            for obj in page.get("Contents", []):
                objects.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    }
                )

        return objects

    def print_objects(self, prefix: str = "", bucket: Optional[str] = None) -> None:
        """Вывести список объектов в читаемом виде."""
        objects = self.list_objects(prefix=prefix, bucket=bucket)
        bucket = bucket or self.bucket_name

        if not objects:
            print(f"Бакет «{bucket}» пуст (prefix='{prefix}')")
            return

        print(f"\n{'─'*60}")
        print(f"  Бакет: {bucket}  |  Объектов: {len(objects)}")
        print(f"{'─'*60}")
        print(f"{'Ключ':<40} {'Размер':>10}  {'Изменён'}")
        print(f"{'─'*60}")
        for obj in objects:
            size_str = _human_size(obj["size"])
            date_str = obj["last_modified"].strftime("%Y-%m-%d %H:%M")
            print(f"{obj['key']:<40} {size_str:>10}  {date_str}")
        print(f"{'─'*60}\n")

    def get_object_info(self, object_key: str, bucket: Optional[str] = None) -> dict:
        """Получить метаданные объекта (HEAD запрос)."""
        bucket = bucket or self._require_bucket()
        resp = self.s3.head_object(Bucket=bucket, Key=object_key)
        return {
            "key": object_key,
            "size": resp["ContentLength"],
            "content_type": resp.get("ContentType"),
            "last_modified": resp["LastModified"],
            "etag": resp["ETag"].strip('"'),
            "metadata": resp.get("Metadata", {}),
        }

    # ──────────────────────────────────────────
    # СКАЧИВАНИЕ ФАЙЛОВ
    # ──────────────────────────────────────────

    def download_file(
        self,
        object_key: str,
        local_path: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> str:
        """
        Скачать файл из R2 на диск.

        Args:
            object_key: Ключ объекта в бакете.
            local_path: Куда сохранить. По умолчанию — текущая папка + имя файла.
            bucket:     Имя бакета.

        Returns:
            Путь к сохранённому файлу.
        """
        bucket = bucket or self._require_bucket()
        local_path = local_path or Path(object_key).name

        # Создать промежуточные директории если нужно
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        print(f"⬇  Скачивание: s3://{bucket}/{object_key} → {local_path}")
        self.s3.download_file(bucket, object_key, local_path)
        print(f"✓  Сохранено: {local_path}")
        return local_path

    def download_bytes(self, object_key: str, bucket: Optional[str] = None) -> bytes:
        """Скачать объект в память и вернуть bytes."""
        bucket = bucket or self._require_bucket()
        print(f"⬇  Чтение в память: s3://{bucket}/{object_key}")
        resp = self.s3.get_object(Bucket=bucket, Key=object_key)
        data = resp["Body"].read()
        print(f"✓  Получено {_human_size(len(data))}")
        return data

    def generate_presigned_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
        operation: str = "get_object",
    ) -> str:
        """
        Сгенерировать временную ссылку для доступа к объекту.

        Args:
            object_key: Ключ объекта.
            expires_in: Время жизни ссылки в секундах (по умолчанию 1 час).
            operation:  'get_object' или 'put_object'.

        Returns:
            URL строка.
        """
        bucket = bucket or self._require_bucket()
        url = self.s3.generate_presigned_url(
            operation,
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
        print(f"🔗  Presigned URL ({expires_in}с): {url}")
        return url

    # ──────────────────────────────────────────
    # УДАЛЕНИЕ ФАЙЛОВ
    # ──────────────────────────────────────────

    def delete_object(self, object_key: str, bucket: Optional[str] = None) -> None:
        """Удалить один объект из бакета."""
        bucket = bucket or self._require_bucket()
        print(f"🗑  Удаление: s3://{bucket}/{object_key}")
        self.s3.delete_object(Bucket=bucket, Key=object_key)
        print(f"✓  Удалено: {object_key}")

    def delete_objects(self, object_keys: list[str], bucket: Optional[str] = None) -> dict:
        """
        Удалить несколько объектов за один запрос (до 1000 ключей).

        Returns:
            Словарь с ключами 'deleted' и 'errors'.
        """
        bucket = bucket or self._require_bucket()

        if not object_keys:
            return {"deleted": [], "errors": []}

        # R2/S3 принимает максимум 1000 ключей за раз
        results = {"deleted": [], "errors": []}
        for chunk in _chunks(object_keys, 1000):
            delete_payload = {"Objects": [{"Key": k} for k in chunk], "Quiet": False}
            print(f"🗑  Удаление {len(chunk)} объектов из «{bucket}»...")
            resp = self.s3.delete_objects(Bucket=bucket, Delete=delete_payload)

            for item in resp.get("Deleted", []):
                results["deleted"].append(item["Key"])
            for item in resp.get("Errors", []):
                results["errors"].append({"key": item["Key"], "message": item["Message"]})

        print(f"✓  Удалено: {len(results['deleted'])}  |  Ошибок: {len(results['errors'])}")
        return results

    def delete_prefix(self, prefix: str, bucket: Optional[str] = None) -> int:
        """
        Удалить все объекты с заданным префиксом.

        Returns:
            Количество удалённых объектов.
        """
        bucket = bucket or self._require_bucket()
        objects = self.list_objects(prefix=prefix, bucket=bucket)
        if not objects:
            print(f"Нет объектов с префиксом «{prefix}»")
            return 0

        keys = [o["key"] for o in objects]
        result = self.delete_objects(keys, bucket=bucket)
        return len(result["deleted"])

    # ──────────────────────────────────────────
    # БАКЕТЫ
    # ──────────────────────────────────────────

    def list_buckets(self) -> list[str]:
        """Получить список всех бакетов."""
        resp = self.s3.list_buckets()
        return [b["Name"] for b in resp.get("Buckets", [])]

    def bucket_exists(self, bucket: Optional[str] = None) -> bool:
        """Проверить существование бакета."""
        bucket = bucket or self._require_bucket()
        try:
            self.s3.head_bucket(Bucket=bucket)
            return True
        except ClientError:
            return False

    # ──────────────────────────────────────────
    # ВСПОМОГАТЕЛЬНОЕ
    # ──────────────────────────────────────────

    def _require_bucket(self) -> str:
        if not self.bucket_name:
            raise ValueError(
                "Имя бакета не задано. Передайте bucket= или установите R2_BUCKET_NAME."
            )
        return self.bucket_name


# ──────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────

def _human_size(size: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ПБ"


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# ──────────────────────────────────────────
# Пример использования
# ──────────────────────────────────────────

if __name__ == "__main__":
    # Инициализация клиента
    # Credentials берутся из переменных окружения:
    #   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
    r2 = R2Client()

    # ── Список объектов ──────────────────────
    r2.print_objects()

    # Фильтрация по префиксу
    # r2.print_objects(prefix="images/")

    # ── Загрузка ────────────────────────────
    r2.upload_file("uploads/frame_0038.png", object_key="7085292078/frame_0038.png", content_type="image/png")

    # Загрузка из памяти
    # r2.upload_bytes(b"Hello, R2!", "hello.txt", content_type="text/plain")

    # ── Скачивание ──────────────────────────
    # r2.download_file("uploads/photo.jpg", local_path="downloaded_photo.jpg")

    # Скачать в память
    # data = r2.download_bytes("hello.txt")
    # print(data.decode())

    # Временная ссылка (presigned URL)
    # url = r2.generate_presigned_url("uploads/photo.jpg", expires_in=600)

    # ── Метаданные объекта ───────────────────
    # info = r2.get_object_info("hello.txt")
    # print(info)

    # ── Удаление ────────────────────────────
    # r2.delete_object("hello.txt")

    # Удалить несколько
    # r2.delete_objects(["file1.txt", "file2.txt"])

    # Удалить все объекты с префиксом
    # r2.delete_prefix("uploads/")

    # ── Список бакетов ──────────────────────
    # print(r2.list_buckets())