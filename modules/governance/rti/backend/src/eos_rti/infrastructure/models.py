"""Tables of rti (PRD "Data model"). Every table carries organisation_id, so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this module: applicant
person ids, officers, custodians and the appellate authority are identity person ids, by id only.

Applicant personal data sits in the request row (applicant_*); only rti:request:read holders are shown it."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import (
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

PREFIX = "rti_"

# Column sizes, shared with the request schemas so a value too long is a 422, never a database error.
NAME_LEN = 200  # applicant name, transfer authority name
EMAIL_LEN = 254
PHONE_LEN = 40
SUBJECT_LEN = 200
MODE_LEN = 100  # fee mode
RECEIPT_LEN = 100  # fee receipt reference
NUMBER_LEN = 20  # RTI-000045: prefix (at most 10), a dash and the sequence
TEXT_MAX = 10_000  # upper bound of the Text columns the contract leaves open
ADDRESS_MAX = 1_000
MAX_AMOUNT_DIGITS = 10  # whole-number digits of a fee amount; the column holds 12 digits and 2 decimals


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


def money(value: Decimal | None) -> str | None:
    """A fee amount as the contract's decimal string, always two decimals."""
    return None if value is None else f"{value:.2f}"


class RtiRequest(Base, TenantMixin, TimestampMixin):
    """A request for information (contract Request). Never deleted: it ends as closed or transferred. Overdue and the
    due date are worked out when read, never stored."""

    __tablename__ = f"{PREFIX}request"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_rti_request_number"),
        UniqueConstraint("organisation_id", "seq", name="uq_rti_request_seq"),
        Index("ix_rti_request_status", "organisation_id", "status"),
        Index("ix_rti_request_officer", "organisation_id", "officer_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(Integer)  # 1, 2, 3 ... per organisation
    number: Mapped[str] = mapped_column(String(NUMBER_LEN))
    received_via: Mapped[str] = mapped_column(String(16))
    received_on: Mapped[date] = mapped_column(Date)
    applicant_name: Mapped[str] = mapped_column(String(NAME_LEN))
    applicant_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicant_email: Mapped[str | None] = mapped_column(String(EMAIL_LEN), nullable=True)
    applicant_phone: Mapped[str | None] = mapped_column(String(PHONE_LEN), nullable=True)
    applicant_person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject: Mapped[str] = mapped_column(String(SUBJECT_LEN))
    information_sought: Mapped[str] = mapped_column(Text)
    fee_status: Mapped[str] = mapped_column(String(8))
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=True)
    fee_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fee_mode: Mapped[str | None] = mapped_column(String(MODE_LEN), nullable=True)
    fee_receipt_reference: Mapped[str | None] = mapped_column(String(RECEIPT_LEN), nullable=True)
    officer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(14))
    closure: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Referral(Base, TenantMixin, TimestampMixin):
    """A question to an internal custodian about one request (contract Referral). The custodian sees the question and
    the request number only."""

    __tablename__ = f"{PREFIX}referral"
    __table_args__ = (
        Index("ix_rti_referral_request", "organisation_id", "request_id"),
        Index("ix_rti_referral_custodian", "organisation_id", "custodian_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}request.id"))
    custodian_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(8))
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Response(Base, TenantMixin, TimestampMixin):
    """The response to a request (contract Response); at most one per request."""

    __tablename__ = f"{PREFIX}response"
    __table_args__ = (UniqueConstraint("organisation_id", "request_id", name="uq_rti_response_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}request.id"))
    type: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text)
    grounds: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_on: Mapped[date] = mapped_column(Date)
    dispatch_mode: Mapped[str] = mapped_column(String(16))
    responded_by: Mapped[str] = mapped_column(String(36))


class Transfer(Base, TenantMixin, TimestampMixin):
    """The transfer of a request to another public authority (contract Transfer); at most one per request."""

    __tablename__ = f"{PREFIX}transfer"
    __table_args__ = (UniqueConstraint("organisation_id", "request_id", name="uq_rti_transfer_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}request.id"))
    authority_name: Mapped[str] = mapped_column(String(NAME_LEN))
    authority_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    transferred_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    transferred_by: Mapped[str] = mapped_column(String(36))


class Appeal(Base, TenantMixin, TimestampMixin):
    """The first appeal against the response (contract Appeal); at most one per request."""

    __tablename__ = f"{PREFIX}appeal"
    __table_args__ = (UniqueConstraint("organisation_id", "request_id", name="uq_rti_appeal_request"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}request.id"))
    filed_on: Mapped[date] = mapped_column(Date)
    grounds: Mapped[str] = mapped_column(Text)
    filed_by: Mapped[str] = mapped_column(String(36))
    outcome: Mapped[str | None] = mapped_column(String(14), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed or read what and when (PRD rule: every state change, referral and reply, and every read of a full
    request is audited). Stands in for the audit SDK, which does not exist yet (packages/sdk is empty), as the other
    modules' do; its rows are not in the platform audit trail. Holds ids and the action only, never applicant data or
    request content."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_rti_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (RtiRequest, Referral, Response, Transfer, Appeal, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
