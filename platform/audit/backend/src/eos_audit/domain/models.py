"""The audit record: one row per intentional state change, written once and never altered.

There is deliberately no method here that changes a record. The only sanctioned changes are a redaction
tombstone and a retention prune, and on PostgreSQL a trigger (migration audit_0001) refuses everything else.
"""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

MAX_MODULE = 60
MAX_ACTION = 120
MAX_ENTITY_TYPE = 60
MAX_ENTITY_ID = 120
MAX_SUMMARY = 300
MAX_CLIENT_TOKEN = 120


class AuditRecord(Base, TenantMixin):
    """organisation_id (from TenantMixin) is null for a platform-level action that belongs to no organisation."""

    __tablename__ = "audit_record"
    __table_args__ = (
        Index("ix_audit_record_org_occurred", "organisation_id", "occurred_at"),
        Index("ix_audit_record_org_entity", "organisation_id", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_record_org_module", "organisation_id", "module"),
        # One record per client_token per organisation. On the raw columns this would not hold for platform
        # records: PostgreSQL and SQLite both treat NULLs as distinct in a unique index, so two platform records
        # with the same token would both be accepted. coalesce gives the platform a scope of its own.
        Index("uq_audit_record_org_token", text("coalesce(organisation_id, '')"), "client_token", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)  # null when the system acted
    module: Mapped[str] = mapped_column(String(MAX_MODULE))
    action: Mapped[str] = mapped_column(String(MAX_ACTION))
    entity_type: Mapped[str] = mapped_column(String(MAX_ENTITY_TYPE))
    entity_id: Mapped[str] = mapped_column(String(MAX_ENTITY_ID))
    summary: Mapped[str | None] = mapped_column(String(MAX_SUMMARY), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_token: Mapped[str | None] = mapped_column(String(MAX_CLIENT_TOKEN), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    redacted: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self, actor_name: str | None = None) -> dict:
        out = {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "actor": self.actor,
            "module": self.module,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "summary": self.summary,
            "before": self.before,
            "after": self.after,
            "context": self.context or {},
            "client_token": self.client_token,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "redacted": bool(self.redacted),
        }
        if actor_name is not None:
            out["actor_name"] = actor_name
        return out


TABLE_NAMES = (AuditRecord.__tablename__,)
