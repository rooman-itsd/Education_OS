"""The event envelope (contracts/events.yaml), the delivery state of an outbox row, and its delivery to each
consuming module.

The outbox table itself is eos_core.events.OutboxEvent: every module writes it through eos_core.events.publish(),
so that model lives in packages/core and this module's Alembic chain owns its DDL. EventDelivery is this module's
own table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from eos_core.db import Base, TenantMixin, new_id, utcnow
from eos_core.events import OutboxEvent
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

TABLE_NAMES = ("outbox_event", "event_bus_delivery")

DELIVERED = "delivered"
FAILED = "failed"

State = Literal["pending", "published", "dead_lettered"]


@dataclass(frozen=True)
class Event:
    """What a consumer receives: the envelope, detached from the database row."""

    id: str
    name: str
    version: int
    organisation_id: str | None
    actor: str | None
    occurred_at: datetime
    payload: dict

    @classmethod
    def of(cls, row: OutboxEvent) -> Event:
        return cls(
            id=row.id,
            name=row.name,
            version=row.version or 1,
            organisation_id=row.organisation_id,
            actor=row.actor,
            occurred_at=row.occurred_at,
            payload=dict(row.payload or {}),
        )


def state_of(row: OutboxEvent, max_attempts: int) -> State:
    """Dead-lettered means not delivered after max_attempts tries; it is never retried until replayed."""
    if row.published:
        return "published"
    return "dead_lettered" if (row.attempts or 0) >= max_attempts else "pending"


class EventDelivery(TenantMixin, Base):
    """One consuming module's delivery of one event: the per-module consumer group #83 asks for. A module whose
    handler committed is `delivered` and is never handed that event again, even when another module's failure
    makes the relay retry the event, or an operator replays it. organisation_id is the event's, so row-level
    security scopes these rows like the event itself."""

    __tablename__ = "event_bus_delivery"
    __table_args__ = (
        UniqueConstraint("event_id", "module", name="uq_event_bus_delivery_event_module"),
        Index("ix_event_bus_delivery_event", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("outbox_event.id", ondelete="CASCADE"), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
