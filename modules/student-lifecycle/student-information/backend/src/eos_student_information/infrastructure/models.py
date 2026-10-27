"""SQLAlchemy 2 mapped models for student-information.

Tables:
- student_information_person
- student_information_status_history
- student_information_document
- student_information_id_card
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import sqlalchemy as sa
from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..domain.enums import IdCardStatus, PersonStatus

PREFIX = "student_information_"

IDENTITY_NOT_NULL = sa.text("identity_number IS NOT NULL")
ACTIVE_CARD = sa.text("status = 'issued'")


def as_utc(value: datetime | None) -> datetime | None:
    """Ensures datetime is timezone-aware in UTC (SQLite returns naive datetimes)."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    """Formats datetime or date to ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class Person(Base, TenantMixin, TimestampMixin):
    """Person master record: the aggregate root for learner information."""

    __tablename__ = f"{PREFIX}person"
    __table_args__ = (
        Index(f"ix_{PREFIX}person_organisation_id", "organisation_id"),
        Index(
            "uq_student_info_person_identity",
            "organisation_id",
            "identity_number",
            unique=True,
            sqlite_where=IDENTITY_NOT_NULL,
            postgresql_where=IDENTITY_NOT_NULL,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(60), nullable=True)
    identity_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    guardians: Mapped[list | None] = mapped_column(JSON, nullable=True)
    identity_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=PersonStatus.PENDING.value)
    status_effective_date: Mapped[date] = mapped_column(Date, default=date.today)
    source: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "preferred_name": self.preferred_name,
            "date_of_birth": iso(self.date_of_birth),
            "gender": self.gender,
            "identity_number": self.identity_number,
            "contact": self.contact,
            "guardians": self.guardians or [],
            "identity_user_id": self.identity_user_id,
            "status": self.status,
            "status_effective_date": iso(self.status_effective_date),
            "source": self.source,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class StatusHistoryEntry(Base, TenantMixin):
    """Immutable log of person status changes. Append-only."""

    __tablename__ = f"{PREFIX}status_history"
    __table_args__ = (
        Index(f"ix_{PREFIX}status_history_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}status_history_person_id", "person_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}person.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "person_id": self.person_id,
            "organisation_id": self.organisation_id,
            "status": self.status,
            "reason": self.reason,
            "effective_date": iso(self.effective_date),
            "changed_by": self.changed_by,
            "changed_at": iso(self.changed_at),
        }


class PersonDocument(Base, TenantMixin):
    """Reference to an attached document managed by platform/documents."""

    __tablename__ = f"{PREFIX}document"
    __table_args__ = (
        Index(f"ix_{PREFIX}document_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}document_person_id", "person_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}person.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "person_id": self.person_id,
            "organisation_id": self.organisation_id,
            "type": self.type,
            "document_id": self.document_id,
            "label": self.label,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": iso(self.uploaded_at),
        }


class IdentityCard(Base, TenantMixin):
    """Logical ID card issued to a person."""

    __tablename__ = f"{PREFIX}id_card"
    __table_args__ = (
        Index(f"ix_{PREFIX}id_card_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}id_card_person_id", "person_id"),
        Index(
            "uq_student_info_active_card",
            "organisation_id",
            "person_id",
            unique=True,
            sqlite_where=ACTIVE_CARD,
            postgresql_where=ACTIVE_CARD,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}person.id", ondelete="CASCADE"), nullable=False
    )
    card_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=IdCardStatus.ISSUED.value)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issued_by: Mapped[str] = mapped_column(String(36), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "person_id": self.person_id,
            "organisation_id": self.organisation_id,
            "card_number": self.card_number,
            "status": self.status,
            "expires_at": iso(self.expires_at),
            "issued_by": self.issued_by,
            "issued_at": iso(self.issued_at),
            "revoked_by": self.revoked_by,
            "revoked_at": iso(self.revoked_at),
            "revoked_reason": self.revoked_reason,
        }
        if self.document_id is not None:
            data["document_id"] = self.document_id
        return data


MODELS = (Person, StatusHistoryEntry, PersonDocument, IdentityCard)
TABLES = [m.__table__ for m in MODELS]
