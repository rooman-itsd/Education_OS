"""Own schema: every table is prefixed external_university_portals_ and carries organisation_id with a forced RLS
policy. The transcript is not kept: only the exchange, its file by document id, its hash and what could not be mapped
(by position and reason, never content)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "external_university_portals_"
STATUSES = ("prepared", "sent", "manual_action_required", "delivered_manually", "received", "parsed", "rejected")


def iso(value: datetime | date | None) -> str | None:
    """ISO 8601. SQLite returns datetimes without a zone, so UTC is added before formatting."""
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat() if value else None


class Exchange(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}exchange"
    # The caller's key makes export and import idempotent: one exchange per organisation, key and direction.
    __table_args__ = (
        Index(
            "uq_external_university_portals_exchange_key", "organisation_id", "exchange_key", "direction", unique=True
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    exchange_key: Mapped[str] = mapped_column(String(100))
    partner_id: Mapped[str] = mapped_column(String(60), index=True)
    partner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)  # outbound | inbound
    person_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    format: Mapped[str] = mapped_column(String(12))
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity: Mapped[str | None] = mapped_column(String(10), nullable=True)  # verified | unsigned | failed
    unmapped: Mapped[list] = mapped_column(JSON, default=list)
    caller_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    caller_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    partner_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "exchange_key": self.exchange_key,
            "partner_id": self.partner_id,
            "partner_name": self.partner_name,
            "direction": self.direction,
            "person_id": self.person_id,
            "format": self.format,
            "channel": self.channel,
            "status": self.status,
            "caller_module": self.caller_module,
            "created_at": iso(self.created_at),
            "delivered_on": iso(self.delivered_on),
        }

    def detail(self) -> dict:
        return {
            **self.summary(),
            "document_id": self.document_id,
            "sha256": self.sha256,
            "integrity": self.integrity,
            "unmapped": self.unmapped or [],
            "partner_reference": self.partner_reference,
            "delivered_by": self.delivered_by,
        }


TABLES = (Exchange.__table__,)
