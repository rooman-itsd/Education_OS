"""Application service for documents: upload intent, confirmation, download URLs, and lifecycle."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.models import (
    STATUS_AVAILABLE,
    STATUS_DELETED,
    STATUS_PENDING_UPLOAD,
    Document,
    validate_file_policy,
)
from ..infrastructure.config import load_settings
from ..infrastructure.storage import StoragePort, get_storage

logger = logging.getLogger(__name__)

SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_.-]")


class DocumentError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def sanitize_filename(filename: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", filename.strip())
    return cleaned[:200] or "unnamed_document"


def view_document(doc: Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "organisation_id": doc.organisation_id,
        "title": doc.title,
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "entity_type": doc.entity_type,
        "entity_id": doc.entity_id,
        "uploaded_by": doc.uploaded_by,
        "client_token": doc.client_token,
        "tags": doc.tags or [],
        "created_at": doc.created_at.isoformat() if isinstance(doc.created_at, datetime) else doc.created_at,
        "updated_at": doc.updated_at.isoformat() if isinstance(doc.updated_at, datetime) else doc.updated_at,
    }


def find_by_token(db: Session, organisation_id: str, client_token: str | None) -> Document | None:
    if not client_token:
        return None
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        Document.client_token == client_token,
    )
    return db.execute(stmt).scalars().first()


def request_upload_intent(
    db: Session,
    organisation_id: str,
    actor_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    title: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    client_token: str | None = None,
    tags: list[str] | None = None,
    storage: StoragePort | None = None,
) -> tuple[Document, bool, str, int]:
    """Register upload intent, validate file policy, and return presigned PUT URL."""
    cfg = load_settings()
    store = storage or get_storage(cfg)

    # Validate file policy
    try:
        validate_file_policy(filename, mime_type, size_bytes, cfg.max_file_size_bytes)
    except ValueError as e:
        raise DocumentError(str(e), status=400) from e

    # Check idempotency
    if client_token:
        existing = find_by_token(db, organisation_id, client_token)
        if existing:
            url = store.generate_upload_url(
                existing.bucket,
                existing.storage_path,
                existing.mime_type,
                cfg.url_expires_seconds,
            )
            return existing, False, url, cfg.url_expires_seconds

    doc_id = new_id()
    safe_name = sanitize_filename(filename)
    now = utcnow()
    year_month = now.strftime("%Y/%m")
    storage_path = f"{organisation_id}/{year_month}/{doc_id}/{safe_name}"

    doc = Document(
        id=doc_id,
        organisation_id=organisation_id,
        title=title or filename,
        filename=filename,
        mime_type=mime_type.lower(),
        size_bytes=size_bytes,
        storage_path=storage_path,
        bucket=cfg.minio_bucket,
        status=STATUS_PENDING_UPLOAD,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=actor_id,
        client_token=client_token,
        tags=tags or [],
        created_at=now,
        updated_at=now,
    )
    db.add(doc)

    upload_url = store.generate_upload_url(
        doc.bucket,
        doc.storage_path,
        doc.mime_type,
        cfg.url_expires_seconds,
    )
    return doc, True, upload_url, cfg.url_expires_seconds


def confirm_upload(
    db: Session,
    organisation_id: str,
    actor_id: str,
    document_id: str,
    storage: StoragePort | None = None,
) -> Document:
    """Confirm client finished uploading to storage and mark document available."""
    store = storage or get_storage()
    doc = get_document(db, organisation_id, document_id)
    if not doc:
        raise DocumentError("Document not found", status=404)
    if doc.status == STATUS_DELETED:
        raise DocumentError("Document has been deleted", status=400)

    # In production, check object exists in storage
    if not store.object_exists(doc.bucket, doc.storage_path):
        raise DocumentError("Document file was not found in storage. Upload may not have completed.", status=400)

    doc.status = STATUS_AVAILABLE
    doc.updated_at = utcnow()

    # Publish outbox event
    events.publish(
        db,
        "documents.document.uploaded",
        organisation_id,
        {
            "document_id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
            "entity_type": doc.entity_type,
            "entity_id": doc.entity_id,
            "uploaded_by": doc.uploaded_by,
        },
        actor=actor_id,
    )
    return doc


def get_document(db: Session, organisation_id: str, document_id: str) -> Document | None:
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        Document.id == document_id,
    )
    return db.execute(stmt).scalars().first()


def get_download_url(
    db: Session,
    organisation_id: str,
    actor_id: str,
    document_id: str,
    storage: StoragePort | None = None,
    expires_seconds: int | None = None,
) -> tuple[Document, str, int]:
    """Generate temporary presigned download URL with content-disposition header."""
    cfg = load_settings()
    store = storage or get_storage(cfg)
    exp = expires_seconds or cfg.url_expires_seconds

    doc = get_document(db, organisation_id, document_id)
    if not doc:
        raise DocumentError("Document not found", status=404)
    if doc.status == STATUS_DELETED:
        raise DocumentError("Document has been deleted", status=404)
    if doc.status != STATUS_AVAILABLE:
        raise DocumentError(f"Document is not available for download (status: {doc.status})", status=400)

    url = store.generate_download_url(doc.bucket, doc.storage_path, doc.filename, exp)
    return doc, url, exp


def list_documents(
    db: Session,
    organisation_id: str,
    status: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    uploaded_by: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Document], int]:
    stmt = select(Document).where(Document.organisation_id == organisation_id)
    count_stmt = select(func.count(Document.id)).where(Document.organisation_id == organisation_id)

    if status:
        stmt = stmt.where(Document.status == status)
        count_stmt = count_stmt.where(Document.status == status)
    else:
        # Default: hide deleted documents
        stmt = stmt.where(Document.status != STATUS_DELETED)
        count_stmt = count_stmt.where(Document.status != STATUS_DELETED)

    if entity_type:
        stmt = stmt.where(Document.entity_type == entity_type)
        count_stmt = count_stmt.where(Document.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(Document.entity_id == entity_id)
        count_stmt = count_stmt.where(Document.entity_id == entity_id)
    if uploaded_by:
        stmt = stmt.where(Document.uploaded_by == uploaded_by)
        count_stmt = count_stmt.where(Document.uploaded_by == uploaded_by)

    total = db.execute(count_stmt).scalar() or 0
    items = list(db.execute(stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)).scalars().all())
    return items, total


def delete_document(
    db: Session,
    organisation_id: str,
    actor_id: str,
    document_id: str,
    storage: StoragePort | None = None,
) -> bool:
    """Soft delete document record and delete object from storage."""
    store = storage or get_storage()
    doc = get_document(db, organisation_id, document_id)
    if not doc:
        raise DocumentError("Document not found", status=404)
    if doc.status == STATUS_DELETED:
        return True

    doc.status = STATUS_DELETED
    doc.updated_at = utcnow()

    # Remove binary from storage
    try:
        store.delete_object(doc.bucket, doc.storage_path)
    except Exception as exc:
        # Even if storage delete raises, metadata is marked deleted
        logger.warning("Failed to delete object from storage %s: %s", doc.storage_path, exc)

    # Publish outbox event
    events.publish(
        db,
        "documents.document.deleted",
        organisation_id,
        {
            "document_id": doc.id,
            "filename": doc.filename,
            "deleted_by": actor_id,
        },
        actor=actor_id,
    )
    return True


def direct_upload(
    db: Session,
    organisation_id: str,
    actor_id: str,
    filename: str,
    mime_type: str,
    data: bytes,
    title: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    tags: list[str] | None = None,
    storage: StoragePort | None = None,
) -> Document:
    """Direct server-side upload helper."""
    cfg = load_settings()
    store = storage or get_storage(cfg)
    size_bytes = len(data)

    try:
        validate_file_policy(filename, mime_type, size_bytes, cfg.max_file_size_bytes)
    except ValueError as e:
        raise DocumentError(str(e), status=400) from e

    doc_id = new_id()
    safe_name = sanitize_filename(filename)
    now = utcnow()
    year_month = now.strftime("%Y/%m")
    storage_path = f"{organisation_id}/{year_month}/{doc_id}/{safe_name}"

    store.put_object(cfg.minio_bucket, storage_path, data, mime_type)

    doc = Document(
        id=doc_id,
        organisation_id=organisation_id,
        title=title or filename,
        filename=filename,
        mime_type=mime_type.lower(),
        size_bytes=size_bytes,
        storage_path=storage_path,
        bucket=cfg.minio_bucket,
        status=STATUS_AVAILABLE,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=actor_id,
        tags=tags or [],
        created_at=now,
        updated_at=now,
    )
    db.add(doc)

    events.publish(
        db,
        "documents.document.uploaded",
        organisation_id,
        {
            "document_id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
            "entity_type": doc.entity_type,
            "entity_id": doc.entity_id,
            "uploaded_by": doc.uploaded_by,
        },
        actor=actor_id,
    )
    return doc
