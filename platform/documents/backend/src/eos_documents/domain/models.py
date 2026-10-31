"""Domain models for documents: entities, statuses, and validation rules."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

STATUS_PENDING_UPLOAD = "pending_upload"
STATUS_AVAILABLE = "available"
STATUS_ARCHIVED = "archived"
STATUS_DELETED = "deleted"

ALLOWED_STATUSES = frozenset({STATUS_PENDING_UPLOAD, STATUS_AVAILABLE, STATUS_ARCHIVED, STATUS_DELETED})

# Standard permitted document and media types in higher education
ALLOWED_MIME_TYPES = frozenset(
    {
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "application/json",
        "application/rtf",
        # Images
        "image/jpeg",
        "image/png",
        "image/webp",
        # Archives
        "application/zip",
        "application/x-zip-compressed",
    }
)

BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".sh",
        ".bash",
        ".bin",
        ".dll",
        ".so",
        ".dylib",
        ".dmg",
        ".pkg",
        ".vbs",
        ".scr",
        ".msi",
        ".com",
        ".pif",
        ".application",
    }
)

TABLE_NAMES = ["documents_document"]


def validate_file_policy(filename: str, mime_type: str, size_bytes: int, max_size_bytes: int) -> None:
    """Validate filename extension, MIME type, and size against security policies."""
    ext = PurePosixPath(filename.strip().lower()).suffix
    if ext in BLOCKED_EXTENSIONS:
        raise ValueError(f"File extension '{ext}' is forbidden for security reasons")
    if mime_type.lower() not in ALLOWED_MIME_TYPES:
        raise ValueError(f"MIME type '{mime_type}' is not permitted")
    if size_bytes <= 0:
        raise ValueError("File size must be greater than 0 bytes")
    if size_bytes > max_size_bytes:
        raise ValueError(f"File size {size_bytes} bytes exceeds maximum allowed limit of {max_size_bytes} bytes")


class Document(Base, TenantMixin):
    """Document metadata and object storage pointer."""

    __tablename__ = "documents_document"
    __table_args__ = (
        Index("ix_documents_document_org_status", "organisation_id", "status"),
        Index("ix_documents_document_org_entity", "organisation_id", "entity_type", "entity_id"),
        Index("uq_documents_document_org_token", "organisation_id", "client_token", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=STATUS_PENDING_UPLOAD, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    client_token: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("status", STATUS_PENDING_UPLOAD)
        kwargs.setdefault("tags", [])
        super().__init__(**kwargs)
