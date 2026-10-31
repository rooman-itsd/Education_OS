"""Tables of e-office. One shared schema with the e_office_ prefix; every table carries organisation_id (TenantMixin)
and gets the tenant_isolation row-level-security policy on Postgres. Nothing is deleted: the note sheet, attachments,
movements and the list of people who have held a file only grow (PRD). People are
platform/identity user ids and documents are platform/documents ids, never foreign keys."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "e_office_"


class Category(Base, TenantMixin, TimestampMixin):
    """A file category. Its code is the first part of every file number opened in it."""

    __tablename__ = f"{PREFIX}category"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_e_office_category_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    retention_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class File(Base, TenantMixin, TimestampMixin):
    """An electronic file. `holder_id` is who has it now; `held_since`, `action_required` and `due_on` describe the
    current holding, and `overdue_flagged_at` marks that this holding was reported overdue (once per holding)."""

    __tablename__ = f"{PREFIX}file"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_e_office_file_number"),
        Index("ix_e_office_file_category_year", "organisation_id", "category_id", "year"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    year: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(500))
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"))
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    created_by: Mapped[str] = mapped_column(String(36))
    holder_id: Mapped[str] = mapped_column(String(36), index=True)
    held_since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action_required: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_decision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class FileHolder(Base, TenantMixin):
    """Everyone who has held a file, once each. A file is visible to the people listed here (PRD rule)."""

    __tablename__ = f"{PREFIX}file_holder"
    __table_args__ = (UniqueConstraint("file_id", "user_id", name="uq_e_office_file_holder"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    first_held_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Note(Base, TenantMixin, TimestampMixin):
    """A numbered paragraph of the note sheet. Never edited or deleted."""

    __tablename__ = f"{PREFIX}note"
    __table_args__ = (UniqueConstraint("file_id", "sequence", name="uq_e_office_note_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(String(36))
    attachment_ids: Mapped[list] = mapped_column(JSON)


class Attachment(Base, TenantMixin, TimestampMixin):
    """A platform/documents id attached to a file. A receipt attached to a file becomes one, carrying its scan (which
    may be missing until the documents service exists)."""

    __tablename__ = f"{PREFIX}attachment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="reference")
    receipt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    added_by: Mapped[str] = mapped_column(String(36))


class Movement(Base, TenantMixin):
    """One line of the movement history: created, forwarded, decided, closed or reopened. Never edited or deleted.
    `sequence` orders the lines of one file, also when two are written in the same step (decide and forward)."""

    __tablename__ = f"{PREFIX}movement"
    __table_args__ = (UniqueConstraint("file_id", "sequence", name="uq_e_office_movement_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    from_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    to_user_id: Mapped[str] = mapped_column(String(36))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_required: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    held_seconds: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Receipt(Base, TenantMixin, TimestampMixin):
    """Inward correspondence registered by the central registry and sent to one person."""

    __tablename__ = f"{PREFIX}receipt"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_e_office_receipt_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    received_on: Mapped[date] = mapped_column(Date)
    sender: Mapped[str] = mapped_column(String(300))
    sender_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    send_to_user_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(10), default="registered", index=True)
    file_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), nullable=True)
    registered_by: Mapped[str] = mapped_column(String(36))
    attached_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Dispatch(Base, TenantMixin, TimestampMixin):
    """An approved letter from a file, requested by its holder and sent by the central registry."""

    __tablename__ = f"{PREFIX}dispatch"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_e_office_dispatch_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}file.id"), index=True)
    attachment_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}attachment.id"))
    addressee: Mapped[str] = mapped_column(String(300))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36))
    sent_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never note text. Stands in for the audit SDK until it ships, as in procurement."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_e_office_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Category, File, FileHolder, Note, Attachment, Movement, Receipt, Dispatch, AuditEntry)]
