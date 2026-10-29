"""Operator reads and the replay behind contracts/openapi.yaml. Scoping is explicit here as well as by row-level
security: an organisation caller sees only its own events; only the super admin, in platform scope, sees
every organisation's and the platform's own."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from eos_core.db import utcnow
from eos_core.events import OutboxEvent
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.models import State, state_of
from ..infrastructure.config import EventBusConfig
from .relay import pending_filter

audit = logging.getLogger("eos.event_bus.audit")


class EventBusError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


@dataclass(frozen=True)
class Scope:
    """organisation_id None with every_organisation True is the super admin looking across tenants."""

    organisation_id: str | None
    every_organisation: bool = False


def _scoped(q, scope: Scope):
    if scope.every_organisation:
        return q if scope.organisation_id is None else q.where(OutboxEvent.organisation_id == scope.organisation_id)
    return q.where(OutboxEvent.organisation_id == scope.organisation_id)


def _state(q, state: State | None, max_attempts: int):
    if state == "published":
        return q.where(OutboxEvent.published.is_(True))
    if state == "pending":
        return q.where(*pending_filter(max_attempts))
    if state == "dead_lettered":
        return q.where(OutboxEvent.published.is_(False), OutboxEvent.attempts >= max_attempts)
    return q


def list_events(
    db: Session,
    scope: Scope,
    config: EventBusConfig,
    *,
    name: str | None = None,
    state: State | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OutboxEvent], int]:
    q = _state(_scoped(select(OutboxEvent), scope), state, config.max_attempts)
    if name:
        if name.endswith("*"):
            prefix = name[:-1].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            q = q.where(OutboxEvent.name.like(f"{prefix}%", escape="\\"))
        else:
            q = q.where(OutboxEvent.name == name)
    if occurred_from:
        q = q.where(OutboxEvent.occurred_at >= occurred_from)
    if occurred_to:
        q = q.where(OutboxEvent.occurred_at <= occurred_to)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(OutboxEvent.occurred_at.desc(), OutboxEvent.id.desc()).limit(limit).offset(offset))
    return list(rows), total


def get_event(db: Session, scope: Scope, event_id: str) -> OutboxEvent:
    row = db.scalar(_scoped(select(OutboxEvent).where(OutboxEvent.id == event_id), scope))
    if row is None:
        raise EventBusError(404, "no such event")  # another organisation's event is not found, not forbidden
    return row


def replay(db: Session, scope: Scope, config: EventBusConfig, event_id: str, actor: str) -> OutboxEvent:
    """Only a dead-lettered event: replaying a delivered one would re-trigger every consumer."""
    row = get_event(db, scope, event_id)
    if state_of(row, config.max_attempts) != "dead_lettered":
        raise EventBusError(409, "only a dead-lettered event can be replayed")
    row.attempts, row.last_error, row.next_attempt_at = 0, None, None
    db.commit()
    # platform/audit does not exist yet (#317); until it does the replay is recorded on this log.
    audit.info("event %s (%s) replayed by %s", row.id, row.name, actor)
    return row


def health(db: Session, config: EventBusConfig, transport: str) -> dict:
    pending = pending_filter(config.max_attempts)
    backlog = db.scalar(select(func.count()).select_from(OutboxEvent).where(*pending)) or 0
    dead = db.scalar(
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.published.is_(False), OutboxEvent.attempts >= config.max_attempts)
    )
    oldest = db.scalar(select(func.min(OutboxEvent.occurred_at)).where(*pending))
    now = utcnow()
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=now.tzinfo)  # SQLite returns naive datetimes; every stored time is UTC
    return {
        "transport": transport,
        "backlog": backlog,
        "dead_lettered": dead or 0,
        "oldest_unpublished_at": oldest.isoformat() if oldest else None,
        "stalled": bool(oldest and (now - oldest).total_seconds() > config.stall_threshold_s),
    }


def event_out(row: OutboxEvent, config: EventBusConfig) -> dict:
    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": row.id,
        "name": row.name,
        "version": row.version or 1,
        "organisation_id": row.organisation_id,
        "actor": row.actor,
        "occurred_at": iso(row.occurred_at),
        "payload": row.payload or {},
        "state": state_of(row, config.max_attempts),
        "attempts": row.attempts or 0,
        "last_error": row.last_error,
        "published_at": iso(row.published_at),
    }
