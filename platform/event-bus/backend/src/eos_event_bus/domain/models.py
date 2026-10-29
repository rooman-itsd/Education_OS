"""The event envelope (contracts/events.yaml) and the delivery state of an outbox row.

The table itself is eos_core.events.OutboxEvent: every module writes it through eos_core.events.publish(), so
the model lives in packages/core and this module's Alembic chain owns its DDL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from eos_core.events import OutboxEvent

TABLE_NAMES = ("outbox_event",)

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
