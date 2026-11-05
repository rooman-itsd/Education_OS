"""Tables owned by search (docs/prd.md, decision 9). The index itself is not a source of truth and is never read
to answer anything but a search. Every table carries organisation_id NOT NULL and gets the forced
tenant_isolation row-level-security policy from eos_core.init_db or the Alembic chain."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

TABLE_NAMES = ("search_reindex_job", "search_index_state", "search_entitlement", "search_dead_letter")

QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED = "queued", "running", "succeeded", "failed", "cancelled"
STATUSES = (QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED)
ACTIVE = (QUEUED, RUNNING)


class ReindexJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "search_reindex_job"
    __table_args__ = (
        CheckConstraint("organisation_id <> ''", name="ck_search_reindex_job_org_nonempty"),
        # One queued or running job per organisation, module and type (scope_key is "<module>|<type or empty>").
        Index(
            "uq_search_reindex_job_active",
            "organisation_id",
            "scope_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_search_reindex_job_listing", "organisation_id", "requested_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    module: Mapped[str] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(130), nullable=True)
    scope_key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default=QUEUED)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents_indexed: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class IndexState(Base, TenantMixin, TimestampMixin):
    __tablename__ = "search_index_state"
    __table_args__ = (
        UniqueConstraint("organisation_id", "type_key", name="uq_search_index_state_org_type"),
        CheckConstraint("organisation_id <> ''", name="ck_search_index_state_org_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    type_key: Mapped[str] = mapped_column(String(130))
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reindex_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Entitlement(Base, TenantMixin, TimestampMixin):
    """Search's copy of the modules an organisation may use, kept from tenancy.entitlement.changed (PRD open
    question 9). Absent: not known yet, and no module is filtered out on that account."""

    __tablename__ = "search_entitlement"
    __table_args__ = (
        UniqueConstraint("organisation_id", name="uq_search_entitlement_org"),
        CheckConstraint("organisation_id <> ''", name="ck_search_entitlement_org_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    modules: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DeadLetter(Base, TenantMixin, TimestampMixin):
    """A document that failed every retry (or was refused). Counted in /platform/health; a reindex of its
    organisation and module repairs and clears it. Holds ids and a short reason code, never content."""

    __tablename__ = "search_dead_letter"
    __table_args__ = (
        UniqueConstraint("organisation_id", "type_key", "record_id", name="uq_search_dead_letter_record"),
        CheckConstraint("organisation_id <> ''", name="ck_search_dead_letter_org_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    module: Mapped[str] = mapped_column(String(64))
    type_key: Mapped[str] = mapped_column(String(130))
    record_id: Mapped[str] = mapped_column(String(128))
    event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(60))
