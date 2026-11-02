"""Application service tests for documents: upload intent, confirmation, download URLs, and outbox events."""

import pytest
from eos_core.events import OutboxEvent
from eos_documents.application import service
from eos_documents.application.service import DocumentError
from eos_documents.domain.models import (
    STATUS_AVAILABLE,
    STATUS_DELETED,
    STATUS_PENDING_UPLOAD,
)
from sqlalchemy import select


def test_upload_intent_and_idempotency(db, org, memory_storage):
    # 1. New upload intent
    doc, created, url, exp = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.faculty_id,
        filename="lecture1.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        title="Lecture 1 Slides",
        client_token="token-xyz",
        storage=memory_storage,
    )
    db.commit()

    assert created is True
    assert doc.status == STATUS_PENDING_UPLOAD
    assert "upload=1" in url
    assert doc.client_token == "token-xyz"
    assert doc.organisation_id == org.id

    # 2. Replay with same token returns existing doc
    doc2, created2, url2, _ = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.faculty_id,
        filename="lecture1.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        client_token="token-xyz",
        storage=memory_storage,
    )
    assert created2 is False
    assert doc2.id == doc.id


def test_confirm_upload_lifecycle(db, org, memory_storage):
    payload = b"%PDF-1.4 simulated pdf"
    doc, _, _, _ = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.student_id,
        filename="assignment.pdf",
        mime_type="application/pdf",
        size_bytes=len(payload),
        storage=memory_storage,
    )
    db.commit()

    # Confirm before file is in storage fails
    with pytest.raises(DocumentError, match="not found in storage"):
        service.confirm_upload(db, org.id, org.student_id, doc.id, storage=memory_storage)

    # Put object in storage simulating client PUT
    memory_storage.put_object(doc.bucket, doc.storage_path, payload, doc.mime_type)

    # Confirm succeeds
    doc = service.confirm_upload(db, org.id, org.student_id, doc.id, storage=memory_storage)
    db.commit()

    assert doc.status == STATUS_AVAILABLE

    # Outbox event published
    evs = [
        e
        for e in db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.document.uploaded"))
        .scalars()
        .all()
        if e.payload.get("document_id") == doc.id
    ]
    assert len(evs) == 1


def test_download_url_generation(db, org, memory_storage):
    notes_data = b"test notes content"
    doc, _, _, _ = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.faculty_id,
        filename="notes.pdf",
        mime_type="application/pdf",
        size_bytes=len(notes_data),
        storage=memory_storage,
    )
    db.commit()

    # Cannot get download URL while pending
    with pytest.raises(DocumentError, match="not available for download"):
        service.get_download_url(db, org.id, org.faculty_id, doc.id, storage=memory_storage)

    # Complete upload
    memory_storage.put_object(doc.bucket, doc.storage_path, notes_data, doc.mime_type)
    service.confirm_upload(db, org.id, org.faculty_id, doc.id, storage=memory_storage)
    db.commit()

    # Now download URL is issued
    _, dl_url, exp = service.get_download_url(db, org.id, org.faculty_id, doc.id, storage=memory_storage)
    assert "download=1" in dl_url
    assert "notes.pdf" in dl_url


def test_list_and_filter_documents(db, org, memory_storage):
    doc1 = service.direct_upload(
        db,
        org.id,
        org.faculty_id,
        "syllabus.pdf",
        "application/pdf",
        b"data1",
        entity_type="course",
        entity_id="c-101",
        storage=memory_storage,
    )
    doc2 = service.direct_upload(
        db,
        org.id,
        org.faculty_id,
        "lab.pdf",
        "application/pdf",
        b"data2",
        entity_type="course",
        entity_id="c-102",
        storage=memory_storage,
    )
    assert doc2.id != doc1.id
    db.commit()

    # Filter by entity_id
    items, total = service.list_documents(db, org.id, entity_id="c-101")
    assert total == 1
    assert items[0].id == doc1.id

    # Filter by entity_type
    items, total = service.list_documents(db, org.id, entity_type="course")
    assert total == 2


def test_delete_document_and_outbox(db, org, memory_storage):
    doc = service.direct_upload(
        db,
        org.id,
        org.admin_id,
        "old_policy.pdf",
        "application/pdf",
        b"content",
        storage=memory_storage,
    )
    db.commit()

    assert memory_storage.object_exists(doc.bucket, doc.storage_path) is True

    # Delete
    deleted = service.delete_document(db, org.id, org.admin_id, doc.id, storage=memory_storage)
    db.commit()

    assert deleted is True
    assert doc.status == STATUS_DELETED
    assert memory_storage.object_exists(doc.bucket, doc.storage_path) is False

    # Outbox event published for deletion
    evs = list(db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.document.deleted")).scalars().all())
    assert len(evs) == 1
    assert evs[0].payload["document_id"] == doc.id


def test_event_publishing_and_transactional_rollback(db, org, memory_storage):
    initial_events = len(list(db.execute(select(OutboxEvent)).scalars().all()))

    _ = service.direct_upload(
        db,
        org.id,
        org.admin_id,
        "temp.pdf",
        "application/pdf",
        b"temp content",
        storage=memory_storage,
    )
    db.flush()

    # Event is present in session
    in_session = len(list(db.execute(select(OutboxEvent)).scalars().all()))
    assert in_session == initial_events + 1

    # Rollback removes the event and doc
    db.rollback()
    after_rollback = len(list(db.execute(select(OutboxEvent)).scalars().all()))
    assert after_rollback == initial_events
