"""Own schema `digilocker_*`. Every table carries organisation_id (TenantMixin) and, on Postgres, a forced
tenant_isolation policy (db/migrations)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

STATUSES = ("pushed", "available_for_pull", "pending_holder_account", "withdrawn", "failed")
SERVED_STATUSES = ("pushed", "available_for_pull", "pending_holder_account")


def iso(value: datetime | date | None) -> str | None:
    """ISO 8601. Datetimes are UTC; SQLite returns them without a zone, so one is added before formatting."""
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat() if value else None


class IssuedDocument(Base, TenantMixin):
    """One document an institution issued, as DigiLocker can ask for it. No search value, mobile number or Aadhaar
    is stored: search keys are kept as a keyed hash, the holder as a normalised name and date of birth."""

    __tablename__ = "digilocker_issued_document"
    __table_args__ = (
        UniqueConstraint("organisation_id", "issuance_key", name="uq_digilocker_doc_issuance_key"),
        UniqueConstraint("organisation_id", "doc_kind", "document_number", name="uq_digilocker_doc_number"),
        UniqueConstraint("organisation_id", "uri", name="uq_digilocker_doc_uri"),
        Index("ix_digilocker_doc_lookup", "organisation_id", "doc_type", "search_key_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issuance_key: Mapped[str] = mapped_column(String(100))
    doc_kind: Mapped[str] = mapped_column(String(40))
    doc_type: Mapped[str] = mapped_column(String(40))
    uri: Mapped[str] = mapped_column(String(200))
    document_id: Mapped[str] = mapped_column(String(36))
    sha256: Mapped[str] = mapped_column(String(64))
    document_number: Mapped[str] = mapped_column(String(60))
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    holder_name_normalised: Mapped[str] = mapped_column(String(200))
    holder_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    search_key_hash: Mapped[str] = mapped_column(String(64))
    # The holder's DigiLocker id, kept only when it is known, because update and delete pushes need it.
    wallet_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A push (A add, U update, D delete) that still has to reach DigiLocker; cleared when it is accepted, so a
    # retried operation sends it again instead of assuming it went through.
    push_pending: Mapped[str | None] = mapped_column(String(1), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="available_for_pull", index=True)
    issued_on: Mapped[date] = mapped_column(Date)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "issuance_key": self.issuance_key,
            "doc_kind": self.doc_kind,
            "provider_doc_type": self.doc_type,
            "person_id": self.person_id,
            "document_number": self.document_number,
            "uri": self.uri,
            "status": self.status,
            "issued_on": iso(self.issued_on),
            "pushed_at": iso(self.pushed_at),
            "last_pulled_at": iso(self.last_pulled_at),
            "withdrawn_at": iso(self.withdrawn_at),
        }


class PullRequestLog(Base, TenantMixin):
    """Every Pull URI and Pull Doc request answered. No search values, no Aadhaar."""

    __tablename__ = "digilocker_pull_request_log"
    __table_args__ = (UniqueConstraint("organisation_id", "channel", "txn", name="uq_digilocker_pull_txn"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    txn: Mapped[str] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(20))  # pull-uri | pull-doc
    doc_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class IssuanceHistory(Base, TenantMixin):
    """Append-only trail of every state change to an issued document, written in the same transaction as the
    change. The adapter publishes no events of its own (contracts/events.yaml); the hub publishes the port events
    and platform/audit records them, so this is the adapter's own record for support."""

    __tablename__ = "digilocker_issuance_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issued_document_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(30))  # issued | replaced | withdrawn | pushed | push_failed
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # codes and statuses only, never personal data
    delivery_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Used by the Alembic chain (db/migrations) to touch only this adapter's tables.
PREFIX = "digilocker_"
TABLES = [m.__table__ for m in (IssuedDocument, PullRequestLog, IssuanceHistory)]
