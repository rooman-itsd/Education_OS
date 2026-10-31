"""Configuration for the documents service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentsSettings:
    storage_backend: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_bucket: str
    max_file_size_bytes: int
    url_expires_seconds: int


def load_settings() -> DocumentsSettings:
    return DocumentsSettings(
        storage_backend=os.getenv("DOCUMENTS_STORAGE_BACKEND", "memory").lower(),
        minio_endpoint=os.getenv("DOCUMENTS_MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("DOCUMENTS_MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("DOCUMENTS_MINIO_SECRET_KEY", "minioadmin"),
        minio_secure=os.getenv("DOCUMENTS_MINIO_SECURE", "false").lower() == "true",
        minio_bucket=os.getenv("DOCUMENTS_MINIO_BUCKET", "eos-documents"),
        max_file_size_bytes=int(os.getenv("DOCUMENTS_MAX_FILE_SIZE_BYTES", "52428800")),  # 50MB
        url_expires_seconds=int(os.getenv("DOCUMENTS_URL_EXPIRES_SECONDS", "900")),  # 15m
    )
