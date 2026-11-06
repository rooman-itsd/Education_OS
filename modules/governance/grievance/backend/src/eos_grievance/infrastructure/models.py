"""Tables of grievance (docs/prd.md "Data model"). Every table carries organisation_id (TenantMixin), so eos_core applies
the row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: person ids (complainant, respondent, members, authors) come from identity, by id only.

Case text (description, respondent, proceedings, updates, decision, appeal) lives only in these tables; it is never
copied into events, audit entries or notices."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "grievance_"

# Column sizes, shared with the request schemas so a value too long is a 422, never a database error.
NAME_LEN = 120  # Committee.name
CATEGORY_LEN = 80  # Grievance.category
RESPONDENT_LEN = 500  # Respondent.description
REASON_LEN = 2000  # withdraw, not-admitted and transfer reasons, kept on the case or in the audit entry
TEXT_LEN = 20_000  # description, update body, proceeding summary, findings, actions, appeal reason and note
MAX_MEMBERS = 200  # per committee


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


class Committee(Base, TenantMixin, TimestampMixin):
    """A committee of one kind (sgrc, anti_ragging, icc, ombudsperson). Deactivated, never deleted."""

    __tablename__ = f"{PREFIX}committee"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_grievance_committee_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(NAME_LEN))
    kind: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CommitteeMember(Base, TenantMixin):
    """A person on a committee. The member list is replaced as a whole when it changes."""

    __tablename__ = f"{PREFIX}committee_member"
    __table_args__ = (
        UniqueConstraint("organisation_id", "committee_id", "person_id", name="uq_grievance_member"),
        Index("ix_grievance_member_person", "organisation_id", "person_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    committee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}committee.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))


class Grievance(Base, TenantMixin, TimestampMixin):
    """A case. due_at, overdue and can_appeal are worked out when read, never stored."""

    __tablename__ = f"{PREFIX}case"
    __table_args__ = (
        UniqueConstraint("organisation_id", "sequence", name="uq_grievance_case_sequence"),
        Index("ix_grievance_case_committee_status", "organisation_id", "committee_id", "status"),
        Index("ix_grievance_case_complainant", "organisation_id", "complainant_id", "filed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sequence: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(24))
    track: Mapped[str] = mapped_column(String(20))
    committee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}committee.id"))
    complainant_id: Mapped[str] = mapped_column(String(36))
    respondent_person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    respondent_description: Mapped[str | None] = mapped_column(String(RESPONDENT_LEN), nullable=True)
    category: Mapped[str] = mapped_column(String(CATEGORY_LEN))
    description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    closure: Mapped[str | None] = mapped_column(String(12), nullable=True)
    not_admitted_reason: Mapped[str | None] = mapped_column(String(REASON_LEN), nullable=True)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Proceeding(Base, TenantMixin, TimestampMixin):
    """A hearing, statement or note. Visible only to the committee."""

    __tablename__ = f"{PREFIX}proceeding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}case.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    held_on: Mapped[date] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text)
    recorded_by: Mapped[str] = mapped_column(String(36))


class Update(Base, TenantMixin, TimestampMixin):
    """A message on the case, from the committee or the complainant. Both sides see it."""

    __tablename__ = f"{PREFIX}update"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}case.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36))
    from_committee: Mapped[bool] = mapped_column(Boolean)
    body: Mapped[str] = mapped_column(Text)


class Decision(Base, TenantMixin):
    """The committee's decision; one per case."""

    __tablename__ = f"{PREFIX}decision"
    __table_args__ = (Index("uq_grievance_decision_case", "grievance_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}case.id"))
    outcome: Mapped[str] = mapped_column(String(16))
    findings: Mapped[str] = mapped_column(Text)
    actions_recommended: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(36))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Appeal(Base, TenantMixin):
    """An appeal to an ombudsperson committee; one per case."""

    __tablename__ = f"{PREFIX}appeal"
    __table_args__ = (
        Index("uq_grievance_appeal_case", "grievance_id", unique=True),
        Index("ix_grievance_appeal_committee", "organisation_id", "committee_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}case.id"))
    committee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}committee.id"))
    reason: Mapped[str] = mapped_column(Text)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed or read what and when (PRD "Audit"). Stands in for the audit SDK, which does not exist yet
    (packages/sdk is empty), as the other governance modules' audit tables do; its rows are not in the platform audit
    trail. It holds ids and the action, and for a withdrawal, a refusal to admit or a transfer the reason given. Case
    text (description, proceedings, updates, decisions, appeals) is never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_grievance_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(String(REASON_LEN), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Committee, CommitteeMember, Grievance, Proceeding, Update, Decision, Appeal, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
