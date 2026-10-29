"""Tables of library. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module.
person_id refers to identity / student-information / hr-payroll by id only. Money is Numeric(12, 2), never float."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "library_"
MONEY = Numeric(12, 2)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class Title(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}title"
    __table_args__ = (Index("ix_library_title_isbn", "organisation_id", "isbn"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[list] = mapped_column(JSON, default=list)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subjects: Mapped[list] = mapped_column(JSON, default=list)
    kind: Mapped[str] = mapped_column(String(60))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Copy(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}copy"
    __table_args__ = (
        UniqueConstraint("organisation_id", "accession_no", name="uq_library_copy_accession"),
        UniqueConstraint("organisation_id", "barcode", name="uq_library_copy_barcode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}title.id"), index=True)
    accession_no: Mapped[str] = mapped_column(String(60))
    barcode: Mapped[str] = mapped_column(String(60))
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    withdraw_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LoanPolicy(Base, TenantMixin):
    __tablename__ = f"{PREFIX}loan_policy"
    __table_args__ = (UniqueConstraint("organisation_id", "member_category", name="uq_library_policy_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    member_category: Mapped[str] = mapped_column(String(60))
    max_loans: Mapped[int] = mapped_column(Integer)
    loan_days: Mapped[int] = mapped_column(Integer)
    max_renewals: Mapped[int] = mapped_column(Integer)
    fine_per_day: Mapped[Decimal] = mapped_column(MONEY)
    max_unpaid_fines: Mapped[Decimal] = mapped_column(MONEY)
    hold_days: Mapped[int] = mapped_column(Integer)


class Member(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}member"
    __table_args__ = (UniqueConstraint("organisation_id", "person_id", name="uq_library_member_person"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(60))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Loan(Base, TenantMixin):
    __tablename__ = f"{PREFIX}loan"
    __table_args__ = (
        Index("ix_library_loan_person", "organisation_id", "person_id"),
        Index("ix_library_loan_copy_status", "organisation_id", "copy_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    copy_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}copy.id"))
    title_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}title.id"))
    person_id: Mapped[str] = mapped_column(String(36))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[str] = mapped_column(String(36))
    due_on: Mapped[date] = mapped_column(Date)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewals: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), index=True)
    damage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set by the daily job when it publishes library.loan.overdue, so the event goes out once per loan.
    overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reservation(Base, TenantMixin):
    __tablename__ = f"{PREFIX}reservation"
    __table_args__ = (Index("ix_library_reservation_title_status", "organisation_id", "title_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}title.id"))
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20))
    held_copy_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}copy.id"), nullable=True)
    hold_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Fine(Base, TenantMixin):
    __tablename__ = f"{PREFIX}fine"
    __table_args__ = (Index("ix_library_fine_person_status", "organisation_id", "person_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    loan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}loan.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(20), default="open")
    receipt_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    waive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    waived_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DigitalResource(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}digital_resource"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(500))
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(60), nullable=True)
    url: Mapped[str] = mapped_column(String(2000))
    access: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change. Ids and the action only, never personal details.
    Stands in for the audit SDK until it ships."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_library_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Title, Copy, LoanPolicy, Member, Loan, Reservation, Fine, DigitalResource, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
