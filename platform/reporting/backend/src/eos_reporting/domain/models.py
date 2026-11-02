"""Domain models for reporting: definitions, executions, and metric snapshots."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
ALLOWED_STATUSES = frozenset({STATUS_PENDING, STATUS_COMPLETED, STATUS_FAILED})

CATEGORIES = frozenset({"academic", "financial", "administrative", "compliance", "general"})

TABLE_NAMES = (
    "reporting_definition",
    "reporting_execution",
    "reporting_metric_snapshot",
)


class ReportDefinition(TenantMixin, Base):
    """Configuration for standard and custom report types."""

    __tablename__ = "reporting_definition"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    parameters_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_reporting_definition_org_code"),
        Index("ix_reporting_definition_category", "category"),
    )


class ReportExecution(TenantMixin, Base):
    """A single execution run of a report definition."""

    __tablename__ = "reporting_execution"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_PENDING)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    export_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    client_token: Mapped[str | None] = mapped_column(String(120), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_reporting_execution_org_requester_token",
            "organisation_id",
            "requested_by",
            "client_token",
            unique=True,
            postgresql_where=text("client_token IS NOT NULL"),
            sqlite_where=text("client_token IS NOT NULL"),
        ),
        Index("ix_reporting_execution_def_status", "report_definition_id", "status"),
    )


DIMENSIONS = JSON().with_variant(JSONB(), "postgresql")


class MetricFact(TenantMixin, Base):
    """One source event's contribution to one metric: the ingestion ledger snapshots are recalculated from.

    Idempotent: unique per (source_event_id, metric_key), so a redelivered event adds nothing. Aggregate-level only:
    dimensions are each metric's whitelisted keys (programme, academic year, department, ...), never a person's id,
    name or email. source_ref is the source entity's own id where a later event must find this fact again (a faculty
    assignment that ends); it is never a person."""

    __tablename__ = "reporting_metric_fact"
    __table_args__ = (
        UniqueConstraint("source_event_id", "metric_key", name="uq_reporting_metric_fact_event_metric"),
        Index("ix_reporting_metric_fact_org_metric_time", "organisation_id", "metric_key", "occurred_at"),
        Index("ix_reporting_metric_fact_source_ref", "organisation_id", "metric_key", "source_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(96), nullable=False)
    metric_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimensions: Mapped[dict] = mapped_column(DIMENSIONS, nullable=False, default=dict)
    dimensions_key: Mapped[str] = mapped_column(String(512), nullable=False)  # canonical JSON: sums a cell exactly
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MetricSnapshot(TenantMixin, Base):
    """An aggregated metric for one organisation, metric, period and set of dimensions, recalculated from
    MetricFact. organisation_id is the tenant. Unique per (organisation, metric, period, dimensions, schema_version):
    recalculating a cell replaces it, so recalculation (incremental on ingest, or historical on demand) is
    idempotent. schema_version is the metric definition's version (application/metrics.py)."""

    __tablename__ = "reporting_metric_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "metric_key",
            "period_start",
            "period_end",
            "dimensions_key",
            "schema_version",
            name="uq_reporting_metric_snapshot_cell",
        ),
        Index("ix_reporting_metric_snapshot_org_metric_period", "organisation_id", "metric_key", "period_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(96), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    dimensions: Mapped[dict] = mapped_column(DIMENSIONS, nullable=False, default=dict)
    dimensions_key: Mapped[str] = mapped_column(String(512), nullable=False)  # canonical JSON, for the unique key
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def tenant_id(self) -> str | None:
        return self.organisation_id
