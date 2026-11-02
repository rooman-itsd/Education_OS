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
    backend = os.getenv("DOCUMENTS_STORAGE_BACKEND", "memory").lower()
    access_key = os.getenv("DOCUMENTS_MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("DOCUMENTS_MINIO_SECRET_KEY", "minioadmin")

    is_dev = os.getenv("EOS_DEV_MODE", "false").lower() in ("true", "1") or bool(os.getenv("PYTEST_CURRENT_TEST"))
    if not is_dev:
        if backend == "memory":
            raise ValueError("In production, DOCUMENTS_STORAGE_BACKEND cannot use the in-memory storage adapter.")
        if backend == "minio" and (access_key == "minioadmin" or secret_key == "minioadmin"):
            raise ValueError(
                "In production, DOCUMENTS_MINIO_ACCESS_KEY and DOCUMENTS_MINIO_SECRET_KEY must not use default credentials."
            )

    return DocumentsSettings(
        storage_backend=backend,
        minio_endpoint=os.getenv("DOCUMENTS_MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=access_key,
        minio_secret_key=secret_key,
        minio_secure=os.getenv("DOCUMENTS_MINIO_SECURE", "false").lower() == "true",
        minio_bucket=os.getenv("DOCUMENTS_MINIO_BUCKET", "eos-documents"),
        max_file_size_bytes=int(os.getenv("DOCUMENTS_MAX_FILE_SIZE_BYTES", "52428800")),  # 50MB
        url_expires_seconds=int(os.getenv("DOCUMENTS_URL_EXPIRES_SECONDS", "900")),  # 15m
    )
