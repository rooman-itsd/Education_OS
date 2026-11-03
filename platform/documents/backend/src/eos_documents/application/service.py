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
        "version": doc.version or 1,
        "version_of": doc.version_of,
        "superseded_by": doc.superseded_by,
        "client_token": doc.client_token,
        "tags": doc.tags or [],
        "created_at": doc.created_at.isoformat() if isinstance(doc.created_at, datetime) else doc.created_at,
        "updated_at": doc.updated_at.isoformat() if isinstance(doc.updated_at, datetime) else doc.updated_at,
    }


def find_by_token(
    db: Session,
    organisation_id: str,
    client_token: str | None,
    uploaded_by: str | None = None,
) -> Document | None:
    if not client_token:
        return None
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        Document.client_token == client_token,
    )
    if uploaded_by:
        stmt = stmt.where(Document.uploaded_by == uploaded_by)
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
        existing = find_by_token(db, organisation_id, client_token, uploaded_by=actor_id)
        if existing:
            url, exp = upload_url_for(existing, store)
            return existing, False, url, exp

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
        upload_path=_upload_key(organisation_id, doc_id),
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

    upload_url, exp = upload_url_for(doc, store)
    return doc, True, upload_url, exp


def _upload_key(organisation_id: str, document_id: str) -> str:
    """A key of its own for this upload, under the organisation's prefix, never the document's storage_path."""
    return f"{organisation_id}/uploads/{document_id}/{new_id()}"


def upload_url_for(doc: Document, store: StoragePort | None = None) -> tuple[str, int]:
    """A presigned PUT for a document still waiting for its file. Once confirmed there is nothing to upload: a
    replayed intent answers 409 rather than hand out a URL (it used to point at the confirmed file's own key)."""
    if doc.status != STATUS_PENDING_UPLOAD:
        raise DocumentError(
            f"Document is already {doc.status}; upload a new version instead (POST /{doc.id}/versions)", status=409
        )
    cfg = load_settings()
    store = store or get_storage(cfg)
    key = doc.upload_path or doc.storage_path  # rows from before upload_path uploaded to storage_path
    return store.generate_upload_url(doc.bucket, key, doc.mime_type, cfg.url_expires_seconds), cfg.url_expires_seconds


def confirm_upload(
    db: Session,
    organisation_id: str,
    actor_id: str,
    document_id: str,
    storage: StoragePort | None = None,
) -> Document:
    """Confirm client finished uploading to storage and mark document available."""
    store = storage or get_storage()
    doc = get_document(db, organisation_id, document_id, for_update=True)  # concurrent confirms run one at a time
    if not doc:
        raise DocumentError("Document not found", status=404)
    if doc.status == STATUS_DELETED:
        raise DocumentError("Document has been deleted", status=400)

    # Restrict confirmation to original uploader
    if doc.uploaded_by and doc.uploaded_by != actor_id:
        raise DocumentError("Only the original uploader can confirm this upload", status=403)

    # Idempotent no-op if already available
    if doc.status == STATUS_AVAILABLE:
        return doc

    previous = None
    if doc.version_of:
        # Only the current latest version may be superseded, and only once: a second new version confirmed in
        # parallel against the same predecessor is refused rather than forking the history.
        previous = _latest_available(db, organisation_id, doc.version_of, exclude=doc.id, for_update=True)
        if previous is None or previous.version != doc.version - 1:
            raise DocumentError("A newer version was confirmed first; request a new version of the latest", 409)

    # Check object exists and verify upload integrity
    upload_key = doc.upload_path or doc.storage_path
    stat = store.stat_object(doc.bucket, upload_key)
    if stat is None:
        raise DocumentError("Document file was not found in storage. Upload may not have completed.", status=400)

    cfg = load_settings()
    if stat.size > cfg.max_file_size_bytes:
        store.delete_object(doc.bucket, upload_key)
        raise DocumentError(f"Uploaded file exceeds maximum allowed size ({cfg.max_file_size_bytes} bytes)", status=400)

    if doc.size_bytes and doc.size_bytes > 0 and stat.size != doc.size_bytes:
        store.delete_object(doc.bucket, upload_key)
        raise DocumentError(
            f"Uploaded file size ({stat.size} bytes) does not match declared size ({doc.size_bytes} bytes)", status=400
        )

    if stat.content_type and not stat.content_type.startswith(doc.mime_type):
        store.delete_object(doc.bucket, upload_key)
        raise DocumentError(
            f"Uploaded content type ({stat.content_type}) does not match declared mime-type ({doc.mime_type})",
            status=400,
        )

    if upload_key != doc.storage_path:
        # The validated bytes move to the document's own key, which no presigned PUT ever names. A PUT that
        # arrives later (the old URL is valid for a while, or a replay) lands on an upload key nothing reads.
        store.copy_object(doc.bucket, upload_key, doc.storage_path)
        store.delete_object(doc.bucket, upload_key)
    doc.upload_path = None

    doc.size_bytes = stat.size
    doc.status = STATUS_AVAILABLE
    doc.updated_at = utcnow()
    if previous is not None:
        previous.superseded_by = doc.id
        previous.updated_at = doc.updated_at

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


def get_document(db: Session, organisation_id: str, document_id: str, *, for_update: bool = False) -> Document | None:
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        Document.id == document_id,
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.execute(stmt).scalars().first()


# --- versions --------------------------------------------------------------------------------------------------


def _root_id(doc: Document) -> str:
    return doc.version_of or doc.id


def _latest_available(
    db: Session, organisation_id: str, root_id: str, *, exclude: str | None = None, for_update: bool = False
) -> Document | None:
    """The newest confirmed, not deleted, not superseded version of a document."""
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        (Document.id == root_id) | (Document.version_of == root_id),
        Document.status == STATUS_AVAILABLE,
        Document.superseded_by.is_(None),
    )
    if exclude:
        stmt = stmt.where(Document.id != exclude)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.execute(stmt.order_by(Document.version.desc())).scalars().first()


def list_versions(db: Session, organisation_id: str, document_id: str) -> list[Document]:
    """Every version of the document `document_id` belongs to, newest first (deleted ones left out)."""
    doc = get_document(db, organisation_id, document_id)
    if not doc:
        return []
    root = _root_id(doc)
    stmt = select(Document).where(
        Document.organisation_id == organisation_id,
        (Document.id == root) | (Document.version_of == root),
        Document.status != STATUS_DELETED,
    )
    return list(db.execute(stmt.order_by(Document.version.desc())).scalars().all())


def request_new_version(
    db: Session,
    organisation_id: str,
    actor_id: str,
    document_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    client_token: str | None = None,
    storage: StoragePort | None = None,
) -> tuple[Document, bool, str, int]:
    """Upload intent for the next version of a document. Only the latest confirmed version can be followed, and
    only by the person who uploaded the document's first version. The new version is a document of its own
    (pending until confirmed); confirming it supersedes the previous one. Earlier versions stay readable."""
    cfg = load_settings()
    store = storage or get_storage(cfg)
    try:
        validate_file_policy(filename, mime_type, size_bytes, cfg.max_file_size_bytes)
    except ValueError as e:
        raise DocumentError(str(e), status=400) from e

    if client_token:
        existing = find_by_token(db, organisation_id, client_token, uploaded_by=actor_id)
        if existing:
            url, exp = upload_url_for(existing, store)
            return existing, False, url, exp

    base = get_document(db, organisation_id, document_id)
    if not base or base.status == STATUS_DELETED:
        raise DocumentError("Document not found", status=404)
    root = get_document(db, organisation_id, _root_id(base))
    if root is None or root.uploaded_by != actor_id:
        raise DocumentError("Only the document's uploader can add a version", status=403)
    if base.status != STATUS_AVAILABLE or base.superseded_by:
        raise DocumentError("Only the latest confirmed version can be followed by a new one", status=409)

    doc_id = new_id()
    now = utcnow()
    version = (base.version or 1) + 1
    doc = Document(
        id=doc_id,
        organisation_id=organisation_id,
        title=base.title,
        filename=filename,
        mime_type=mime_type.lower(),
        size_bytes=size_bytes,
        storage_path=f"{organisation_id}/{now.strftime('%Y/%m')}/{doc_id}/{sanitize_filename(filename)}",
        upload_path=_upload_key(organisation_id, doc_id),
        bucket=cfg.minio_bucket,
        status=STATUS_PENDING_UPLOAD,
        entity_type=base.entity_type,
        entity_id=base.entity_id,
        uploaded_by=actor_id,
        client_token=client_token,
        tags=list(base.tags or []),
        version=version,
        version_of=_root_id(base),
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    url, exp = upload_url_for(doc, store)
    return doc, True, url, exp


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
    include_superseded: bool = False,
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
    if not include_superseded:
        # One entry per document: its latest version (GET /{id}/versions lists the others)
        stmt = stmt.where(Document.superseded_by.is_(None))
        count_stmt = count_stmt.where(Document.superseded_by.is_(None))

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
