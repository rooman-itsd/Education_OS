"""Domain models for reporting: definitions, executions, and metric snapshots."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Index, String
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
        Index("ix_reporting_definition_org_code", "organisation_id", "code"),
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
        Index("ix_reporting_execution_org_client_token", "organisation_id", "client_token"),
        Index("ix_reporting_execution_def_status", "report_definition_id", "status"),
    )


class MetricSnapshot(TenantMixin, Base):
    """Periodic or aggregated metric snapshots for analytics and MIS widgets."""

    __tablename__ = "reporting_metric_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_reporting_metric_snapshot_org_metric", "organisation_id", "metric_type", "department_id"),
        Index("ix_reporting_metric_snapshot_period", "period"),
    )
