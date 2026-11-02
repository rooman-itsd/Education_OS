"""Unit tests for storage port and memory implementation."""

import pytest
from eos_documents.infrastructure.config import DocumentsSettings
from eos_documents.infrastructure.storage import (
    MemoryStorage,
    MinioStorage,
    StoragePort,
)


def test_memory_storage_implements_storage_port():
    storage: StoragePort = MemoryStorage()

    # Upload URL
    up_url = storage.generate_upload_url("test-bucket", "test-key", "application/pdf", 600)
    assert "upload=1" in up_url
    assert "test-key" in up_url

    # Put and get
    data = b"sample pdf binary content"
    storage.put_object("test-bucket", "test-key", data, "application/pdf")
    assert storage.object_exists("test-bucket", "test-key") is True
    assert storage.object_exists("test-bucket", "non-existent") is False
    assert storage.get_object("test-bucket", "test-key") == data

    # Download URL
    dl_url = storage.generate_download_url("test-bucket", "test-key", "doc.pdf", 600)
    assert "download=1" in dl_url
    assert "doc.pdf" in dl_url

    # Delete
    storage.delete_object("test-bucket", "test-key")
    assert storage.object_exists("test-bucket", "test-key") is False
    with pytest.raises(KeyError):
        storage.get_object("test-bucket", "test-key")


def test_minio_storage_initializes_and_conforms():
    settings = DocumentsSettings(
        storage_backend="minio",
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        minio_secure=False,
        minio_bucket="eos-test",
        max_file_size_bytes=1000000,
        url_expires_seconds=900,
    )
    storage: StoragePort = MinioStorage(settings)
    assert hasattr(storage, "generate_upload_url")
    assert hasattr(storage, "generate_download_url")
    assert hasattr(storage, "put_object")
    assert hasattr(storage, "get_object")
    assert hasattr(storage, "delete_object")
    assert hasattr(storage, "object_exists")
