"""Storage port abstraction and MinIO / Memory implementations."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from minio import Minio

from .config import DocumentsSettings, load_settings

logger = logging.getLogger(__name__)


@dataclass
class ObjectStat:
    size: int
    content_type: str | None


class StoragePort(Protocol):
    """Storage port for object storage operations."""

    def generate_upload_url(self, bucket: str, key: str, mime_type: str, expires_seconds: int = 900) -> str:
        """Generate a presigned PUT URL for client-side direct upload."""
        ...

    def generate_download_url(self, bucket: str, key: str, filename: str, expires_seconds: int = 900) -> str:
        """Generate a presigned GET URL for secure client-side download."""
        ...

    def put_object(self, bucket: str, key: str, data: bytes, mime_type: str) -> None:
        """Store binary data directly."""
        ...

    def get_object(self, bucket: str, key: str) -> bytes:
        """Retrieve binary data directly."""
        ...

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object from storage."""
        ...

    def object_exists(self, bucket: str, key: str) -> bool:
        """Check whether an object exists in storage."""
        ...

    def stat_object(self, bucket: str, key: str) -> ObjectStat | None:
        """Get object metadata (size, content_type) or None if object does not exist."""
        ...


class MinioStorage:
    """MinIO / S3-compatible storage implementation."""

    def __init__(self, settings: DocumentsSettings) -> None:
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.default_bucket = settings.minio_bucket
        self._ensure_bucket(self.default_bucket)

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except Exception as exc:
            # If storage server is not yet accessible at boot, let operations handle errors
            logger.warning("Could not ensure bucket %s exists: %s", bucket, exc)

    def generate_upload_url(self, bucket: str, key: str, mime_type: str, expires_seconds: int = 900) -> str:
        return self.client.get_presigned_url(
            "PUT",
            bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    def generate_download_url(self, bucket: str, key: str, filename: str, expires_seconds: int = 900) -> str:
        safe_filename = filename.replace('"', '\\"')
        return self.client.get_presigned_url(
            "GET",
            bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
            response_headers={"response-content-disposition": f'attachment; filename="{safe_filename}"'},
        )

    def put_object(self, bucket: str, key: str, data: bytes, mime_type: str) -> None:
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=stream,
            length=len(data),
            content_type=mime_type,
        )

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.remove_object(bucket, key)

    def object_exists(self, bucket: str, key: str) -> bool:
        return self.stat_object(bucket, key) is not None

    def stat_object(self, bucket: str, key: str) -> ObjectStat | None:
        try:
            stat = self.client.stat_object(bucket, key)
            return ObjectStat(size=stat.size, content_type=stat.content_type)
        except Exception:
            return None


class MemoryStorage:
    """Thread-safe in-memory object storage for tests and development."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    def generate_upload_url(self, bucket: str, key: str, mime_type: str, expires_seconds: int = 900) -> str:
        return f"https://storage.local.test/{bucket}/{key}?upload=1&expires={expires_seconds}"

    def generate_download_url(self, bucket: str, key: str, filename: str, expires_seconds: int = 900) -> str:
        return f"https://storage.local.test/{bucket}/{key}?download=1&filename={filename}&expires={expires_seconds}"

    def put_object(self, bucket: str, key: str, data: bytes, mime_type: str) -> None:
        self.objects[(bucket, key)] = (data, mime_type)

    def get_object(self, bucket: str, key: str) -> bytes:
        item = self.objects.get((bucket, key))
        if item is None:
            raise KeyError(f"Object {bucket}/{key} not found")
        return item[0]

    def delete_object(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    def object_exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects

    def stat_object(self, bucket: str, key: str) -> ObjectStat | None:
        item = self.objects.get((bucket, key))
        if item is None:
            return None
        return ObjectStat(size=len(item[0]), content_type=item[1])


_storage_singleton: StoragePort | None = None


def get_storage(settings: DocumentsSettings | None = None) -> StoragePort:
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton
    cfg = settings or load_settings()
    if cfg.storage_backend == "minio":
        _storage_singleton = MinioStorage(cfg)
    else:
        _storage_singleton = MemoryStorage()
    return _storage_singleton


def reset_storage() -> None:
    """Reset the singleton storage instance (used in tests)."""
    global _storage_singleton
    _storage_singleton = None
