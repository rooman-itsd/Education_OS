"""Tests for organisation purge document file cleanup (Finding N9, #676)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from eos_core.events import OutboxEvent
from eos_documents.application import consumers
from eos_documents.infrastructure import config
from eos_documents.infrastructure.storage import MemoryStorage
from sqlalchemy import select


@dataclass
class FakeEvent:
    name: str
    organisation_id: str | None
    payload: dict[str, Any] | None


def test_memory_storage_delete_prefix(memory_storage):
    bucket = "test-bucket"
    memory_storage.put_object(bucket, "org-1/2026/01/doc1.pdf", b"data1", "application/pdf")
    memory_storage.put_object(bucket, "org-1/uploads/temp.pdf", b"data2", "application/pdf")
    memory_storage.put_object(bucket, "org-2/2026/01/doc2.pdf", b"data3", "application/pdf")

    deleted = memory_storage.delete_prefix(bucket, "org-1/")
    assert deleted == 2
    assert not memory_storage.object_exists(bucket, "org-1/2026/01/doc1.pdf")
    assert not memory_storage.object_exists(bucket, "org-1/uploads/temp.pdf")
    assert memory_storage.object_exists(bucket, "org-2/2026/01/doc2.pdf")

    # Deleting non-existent prefix returns 0
    assert memory_storage.delete_prefix(bucket, "org-none/") == 0


def test_on_purged_consumer_deletes_files_and_publishes_event(db, monkeypatch):
    storage = MemoryStorage()
    monkeypatch.setattr("eos_documents.application.consumers.get_storage", lambda cfg=None: storage)
    cfg = config.load_settings()

    org_id_1 = str(uuid.uuid4())
    org_id_2 = str(uuid.uuid4())

    storage.put_object(cfg.minio_bucket, f"{org_id_1}/2026/11/a.pdf", b"a", "application/pdf")
    storage.put_object(cfg.minio_bucket, f"{org_id_1}/uploads/b.pdf", b"b", "application/pdf")
    storage.put_object(cfg.minio_bucket, f"{org_id_2}/2026/11/c.pdf", b"c", "application/pdf")

    event = FakeEvent(
        name="tenancy.organisation.purged",
        organisation_id=None,
        payload={"organisation_id": org_id_1, "slug": "test-org"},
    )

    consumers.on_purged(db, event)
    db.flush()

    # Org 1 storage objects are gone, Org 2 remains
    assert not storage.object_exists(cfg.minio_bucket, f"{org_id_1}/2026/11/a.pdf")
    assert not storage.object_exists(cfg.minio_bucket, f"{org_id_1}/uploads/b.pdf")
    assert storage.object_exists(cfg.minio_bucket, f"{org_id_2}/2026/11/c.pdf")

    # Event published
    evs = list(
        db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.organisation.purged")).scalars().all()
    )
    assert len(evs) == 1
    assert evs[0].payload["organisation_id"] == org_id_1
    assert evs[0].payload["objects_deleted"] == 2


def test_on_purged_ignores_invalid_uuid(db, monkeypatch):
    storage = MemoryStorage()
    monkeypatch.setattr("eos_documents.application.consumers.get_storage", lambda cfg=None: storage)

    for invalid in [None, "", "not-a-uuid", 12345]:
        event = FakeEvent(
            name="tenancy.organisation.purged",
            organisation_id=None,
            payload={"organisation_id": invalid},
        )
        consumers.on_purged(db, event)

    db.flush()
    evs = list(
        db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.organisation.purged")).scalars().all()
    )
    assert len(evs) == 0


def test_consumers_dict_registers_tenancy_organisation_purged():
    assert "tenancy.organisation.purged" in consumers.CONSUMERS
    assert consumers.CONSUMERS["tenancy.organisation.purged"] is consumers.on_purged


def test_minio_storage_delete_prefix_raises_on_errors():
    from eos_documents.infrastructure.storage import MinioStorage

    class FakeDeleteError:
        def __init__(self, name: str, code: str):
            self.name = name
            self.code = code

    class FakeMinioClient:
        def list_objects(self, bucket: str, prefix: str = "", recursive: bool = False, include_version: bool = False):
            from dataclasses import dataclass

            @dataclass
            class Item:
                object_name: str
                version_id: str | None = None

            return [Item("org-1/file1.pdf"), Item("org-1/file2.pdf")]

        def remove_objects(self, bucket: str, objects):
            return [FakeDeleteError("org-1/file1.pdf", "AccessDenied")]

    storage = MinioStorage.__new__(MinioStorage)
    storage.client = FakeMinioClient()

    import pytest

    with pytest.raises(
        RuntimeError,
        match="Failed to delete 1 objects with prefix org-1/: \\['AccessDenied'\\]",
    ):
        storage.delete_prefix("test-bucket", "org-1/")


def test_on_purged_fails_and_does_not_publish_event_on_storage_error(db, monkeypatch):
    class ErrorStorage(MemoryStorage):
        def delete_prefix(self, bucket: str, prefix: str) -> int:
            raise RuntimeError("Storage error")

    monkeypatch.setattr(
        "eos_documents.application.consumers.get_storage",
        lambda cfg=None: ErrorStorage(),
    )
    org_id = str(uuid.uuid4())
    event = FakeEvent(
        name="tenancy.organisation.purged",
        organisation_id=None,
        payload={"organisation_id": org_id, "slug": "test-org"},
    )
    import pytest

    with pytest.raises(RuntimeError, match="Storage error"):
        consumers.on_purged(db, event)

    db.flush()
    evs = list(
        db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.organisation.purged")).scalars().all()
    )
    assert len(evs) == 0


def test_minio_storage_delete_prefix_removes_every_version_and_delete_marker():
    """On a versioned bucket a plain delete leaves the earlier versions readable: the purge must name each version and
    each delete marker, the 'null' version of an object made before versioning was switched on included."""
    from dataclasses import dataclass

    from eos_documents.infrastructure.storage import MinioStorage

    @dataclass
    class Item:
        object_name: str
        version_id: str | None
        is_delete_marker: bool = False

    listed = [
        Item("org-1/a.pdf", "v2"),
        Item("org-1/a.pdf", "v1"),
        Item("org-1/a.pdf", "mk1", is_delete_marker=True),
        Item("org-1/old.pdf", "null"),
        Item("org-1/plain.pdf", None),
    ]

    class FakeMinioClient:
        def __init__(self):
            self.list_kwargs = None
            self.removed = None

        def list_objects(self, bucket, prefix="", recursive=False, include_version=False):
            self.list_kwargs = {"bucket": bucket, "prefix": prefix, "recursive": recursive, "version": include_version}
            return listed if include_version else [i for i in listed if i.version_id in (None, "v2")]

        def remove_objects(self, bucket, objects):
            self.removed = sorted((o.name, o.version_id) for o in objects)
            return []

    storage = MinioStorage.__new__(MinioStorage)
    storage.client = FakeMinioClient()

    assert storage.delete_prefix("bucket", "org-1/") == 5
    assert storage.client.list_kwargs == {"bucket": "bucket", "prefix": "org-1/", "recursive": True, "version": True}
    assert storage.client.removed == [
        ("org-1/a.pdf", "mk1"),
        ("org-1/a.pdf", "v1"),
        ("org-1/a.pdf", "v2"),
        ("org-1/old.pdf", "null"),
        ("org-1/plain.pdf", None),
    ]
