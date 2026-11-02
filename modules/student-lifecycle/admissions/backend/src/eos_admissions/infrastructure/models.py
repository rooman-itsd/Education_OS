"""SQLAlchemy models for admissions. Every table is prefixed admissions_ and carries organisation_id; the
migration puts the tenant_isolation row-level-security policy on each. to_dict() returns contract field names."""

from __future__ import annotations

from datetime import UTC, date, datetime

import sqlalchemy as sa
from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..domain import enums as e

PREFIX = "admissions_"

OPEN_OFFER = sa.text("status = 'open'")


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every stored datetime is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class Application(Base, TenantMixin):
    __tablename__ = f"{PREFIX}application"
    __table_args__ = (
        Index(f"ix_{PREFIX}application_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}application_reference", "organisation_id", "reference_number", unique=True),
        Index(f"ix_{PREFIX}application_status", "organisation_id", "status"),
        Index(f"ix_{PREFIX}application_programme", "organisation_id", "programme_id", "academic_year"),
        Index(f"ix_{PREFIX}application_applicant_user", "organisation_id", "applicant_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(32), nullable=False)
    applicant_first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    applicant_last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    applicant_email: Mapped[str] = mapped_column(String(320), nullable=False)
    applicant_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    applicant_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The identity user who linked this application to their account (POST /me/applications); None until then.
    applicant_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    programme_id: Mapped[str] = mapped_column(String(36), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    selection_process_round_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    portfolio_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.SUBMITTED)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    def to_dict(self) -> dict:
        """Contract Application without documents and offer, which the service attaches."""
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "reference_number": self.reference_number,
            "applicant": {
                "first_name": self.applicant_first_name,
                "last_name": self.applicant_last_name,
                "email": self.applicant_email,
                "phone": self.applicant_phone,
                "date_of_birth": iso(self.applicant_date_of_birth),
            },
            "programme_id": self.programme_id,
            "academic_year": self.academic_year,
            "selection_process_round_id": self.selection_process_round_id,
            "portfolio_item_id": self.portfolio_item_id,
            "status": self.status,
            "submitted_at": iso(self.submitted_at),
            "decided_at": iso(self.decided_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class ApplicationDocument(Base, TenantMixin):
    __tablename__ = f"{PREFIX}application_document"
    __table_args__ = (
        Index(f"ix_{PREFIX}application_document_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}application_document_application_id", "application_id"),
        Index(f"ix_{PREFIX}application_document_queue", "organisation_id", "verification_status", "uploaded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}application.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.PENDING)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "type": self.type,
            "document_id": self.document_id,
            "label": self.label,
            "verification_status": self.verification_status,
            "verification_note": self.verification_note,
            "verified_by": self.verified_by,
            "verified_at": iso(self.verified_at),
            "uploaded_at": iso(self.uploaded_at),
        }


class Offer(Base, TenantMixin):
    __tablename__ = f"{PREFIX}offer"
    __table_args__ = (
        Index(f"ix_{PREFIX}offer_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}offer_application_id", "application_id"),
        Index(
            f"uq_{PREFIX}offer_open",
            "application_id",
            unique=True,
            sqlite_where=OPEN_OFFER,
            postgresql_where=OPEN_OFFER,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}application.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.OFFER_OPEN)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offered_by: Mapped[str] = mapped_column(String(36), nullable=False)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "status": self.status,
            "note": self.note,
            "expires_at": iso(self.expires_at),
            "offered_by": self.offered_by,
            "offered_at": iso(self.offered_at),
            "decided_at": iso(self.decided_at),
            "decline_reason": self.decline_reason,
        }


class MeritList(Base, TenantMixin):
    __tablename__ = f"{PREFIX}merit_list"
    __table_args__ = (
        Index(f"ix_{PREFIX}merit_list_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}merit_list_programme", "organisation_id", "programme_id", "academic_year"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    programme_id: Mapped[str] = mapped_column(String(36), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        """Contract MeritList without entries, which the service attaches."""
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "programme_id": self.programme_id,
            "academic_year": self.academic_year,
            "title": self.title,
            "status": self.status,
            "published_at": iso(self.published_at),
            "created_at": iso(self.created_at),
        }


class MeritListEntry(Base, TenantMixin):
    __tablename__ = f"{PREFIX}merit_list_entry"
    __table_args__ = (
        Index(f"ix_{PREFIX}merit_list_entry_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}merit_list_entry_application", "merit_list_id", "application_id", unique=True),
        Index(f"uq_{PREFIX}merit_list_entry_rank", "merit_list_id", "rank", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    merit_list_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}merit_list.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}application.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    def to_dict(self) -> dict:
        """Contract MeritListEntry without reference_number, which the service attaches."""
        return {"application_id": self.application_id, "rank": self.rank, "score": self.score}


class AuditEntry(Base, TenantMixin):
    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index(f"ix_{PREFIX}audit_entry_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}audit_entry_entity", "entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


MODELS = (Application, ApplicationDocument, Offer, MeritList, MeritListEntry, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
