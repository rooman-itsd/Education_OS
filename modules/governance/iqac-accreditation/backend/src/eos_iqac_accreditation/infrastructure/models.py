"""Tables of iqac-accreditation (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: owner_id, added_by, reviewed_by and the audit actor are person ids from identity, by id only, and an
evidence reference names a record in another module by id only."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "iqac_accreditation_"

# Column sizes, shared with the request schemas so a value too long is a 422, never a database error.
CODE_LEN = 40  # Framework.code, Metric.code
NAME_LEN = 200  # Framework.name, Cycle.name, ActionItem.title, Evidence.title
METRIC_TITLE_LEN = 500
CRITERION_LEN = 200
UNIT_LEN = 40
SOURCE_LEN = 120  # ActionItem.source
URL_LEN = 2000  # Evidence.url
REFERENCE_PART_LEN = 120  # Reference.module, .entity, .id


class Framework(Base, TenantMixin, TimestampMixin):
    """An accreditation framework the organisation reports against (contract Framework). Deactivated, never deleted."""

    __tablename__ = f"{PREFIX}framework"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_iqac_accreditation_framework_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(CODE_LEN))
    name: Mapped[str] = mapped_column(String(NAME_LEN))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Metric(Base, TenantMixin, TimestampMixin):
    """A metric of a framework (contract Metric). Deactivated, never deleted; responses keep their values."""

    __tablename__ = f"{PREFIX}metric"
    __table_args__ = (
        UniqueConstraint("organisation_id", "framework_id", "code", name="uq_iqac_accreditation_metric_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    framework_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}framework.id"), index=True)
    code: Mapped[str] = mapped_column(String(CODE_LEN))
    title: Mapped[str] = mapped_column(String(METRIC_TITLE_LEN))
    criterion: Mapped[str | None] = mapped_column(String(CRITERION_LEN), nullable=True)
    kind: Mapped[str] = mapped_column(String(14))
    unit: Mapped[str | None] = mapped_column(String(UNIT_LEN), nullable=True)
    guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Cycle(Base, TenantMixin, TimestampMixin):
    """A collection cycle of one framework for one period (contract Cycle)."""

    __tablename__ = f"{PREFIX}cycle"
    __table_args__ = (Index("ix_iqac_accreditation_cycle_framework", "organisation_id", "framework_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    framework_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}framework.id"))
    name: Mapped[str] = mapped_column(String(NAME_LEN))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12))
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Response(Base, TenantMixin, TimestampMixin):
    """The answer to one metric in one cycle, owned by one person (contract Response). One per metric per cycle.
    Overdue is worked out when read, never stored."""

    __tablename__ = f"{PREFIX}response"
    __table_args__ = (
        UniqueConstraint("organisation_id", "cycle_id", "metric_id", name="uq_iqac_accreditation_response_metric"),
        Index("ix_iqac_accreditation_response_owner", "organisation_id", "owner_id", "status"),
        Index("ix_iqac_accreditation_response_due", "organisation_id", "due_on"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cycle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}cycle.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}metric.id"), index=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Evidence(Base, TenantMixin):
    """A link or a reference to a record in another module, added to a response (contract Evidence). Stored as
    given; nothing is checked against the other module. Removed (and audited) only while the response is not
    accepted."""

    __tablename__ = f"{PREFIX}evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    response_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}response.id"), index=True)
    title: Mapped[str] = mapped_column(String(NAME_LEN))
    kind: Mapped[str] = mapped_column(String(9))
    url: Mapped[str | None] = mapped_column(String(URL_LEN), nullable=True)
    reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[str] = mapped_column(String(36))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActionItem(Base, TenantMixin, TimestampMixin):
    """A quality action item (contract ActionItem). Cancelled or done, never deleted."""

    __tablename__ = f"{PREFIX}action_item"
    __table_args__ = (
        Index("ix_iqac_accreditation_action_item_status_due", "organisation_id", "status", "due_on"),
        Index("ix_iqac_accreditation_action_item_owner", "organisation_id", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(NAME_LEN))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(SOURCE_LEN), nullable=True)
    cycle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}cycle.id"), nullable=True)
    metric_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}metric.id"), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(11))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every change (PRD rule "Every state change ... writes an audit record"). Stands
    in for the audit SDK, which does not exist yet (packages/sdk is empty), as regulatory-reports' does; its rows are
    not in the platform audit trail. `reason` keeps a return or review comment, a status move ("planning -> collecting")
    or the note of an action item change. Values, narratives, evidence and links are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_iqac_accreditation_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Framework, Metric, Cycle, Response, Evidence, ActionItem, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
