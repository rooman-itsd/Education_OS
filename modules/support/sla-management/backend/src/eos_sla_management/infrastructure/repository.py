"""Queries, always scoped to the caller's or the event's organisation (eos_core.db.scoped). On Postgres row-level
security enforces the same rule underneath. Every stored time is UTC; on SQLite times come back naive."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime

from eos_core.db import new_id, scoped
from sqlalchemy import ColumnElement, Select, and_, func, not_, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..domain.clocks import RUNNING
from .models import Calendar, Clock, Escalation, Policy, ProcessedEvent, TicketRef

# A cursor is an offset; anything larger is refused, so an OFFSET bind can never overflow.
MAX_OFFSET = 10**6


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str, *, lock: bool = False):
    query = _scoped(db, model).where(model.id == row_id)
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


def _insert(db: Session):
    return postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert


# ---------------------------------------------------------------- pagination (opaque cursor = offset)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """The offset in `cursor`; ValueError when it is not one this module gave out."""
    if not cursor:
        return 0
    if len(cursor) > 32:
        raise ValueError("cursor is not valid")
    try:
        text = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    except (ValueError, UnicodeError, binascii.Error):
        raise ValueError("cursor is not valid") from None
    if not text.isdigit() or int(text) > MAX_OFFSET:
        raise ValueError("cursor is not valid")
    return int(text)


# ---------------------------------------------------------------- calendars and policies


def calendars(db: Session, *, active: bool | None) -> list[Calendar]:
    query = _scoped(db, Calendar)
    if active is not None:
        query = query.where(Calendar.active.is_(active))
    return list(db.scalars(query.order_by(Calendar.name, Calendar.id)))


def calendars_by_id(db: Session, ids: set[str]) -> dict[str, Calendar]:
    if not ids:
        return {}
    return {c.id: c for c in db.scalars(_scoped(db, Calendar).where(Calendar.id.in_(ids)))}


def policies(
    db: Session, *, priority: str | None = None, category_id: str | None = None, active: bool | None = None
) -> list[Policy]:
    query = _scoped(db, Policy)
    if priority is not None:
        query = query.where(Policy.priority == priority)
    if category_id is not None:
        query = query.where(Policy.category_id == category_id)
    if active is not None:
        query = query.where(Policy.active.is_(active))
    return list(db.scalars(query.order_by(Policy.priority, Policy.name, Policy.id)))


def active_policy_for(db: Session, priority: str, category_id: str | None, *, other_than: str | None = None):
    """The active policy holding (priority, category), if any."""
    key = category_id or "*"
    query = _scoped(db, Policy).where(Policy.active.is_(True), Policy.priority == priority, Policy.category_key == key)
    if other_than is not None:
        query = query.where(Policy.id != other_than)
    return db.scalars(query).first()


def active_policies_using(db: Session, calendar_id: str) -> list[Policy]:
    query = _scoped(db, Policy).where(Policy.calendar_id == calendar_id, Policy.active.is_(True))
    return list(db.scalars(query))


# ---------------------------------------------------------------- helpdesk events


def mark_processed(db: Session, organisation_id: str, event_id: str, name: str) -> bool:
    """Record a helpdesk event as applied; False when it already was. INSERT ... ON CONFLICT DO NOTHING, so a
    concurrent delivery of the same event waits for the first and then finds the row, instead of failing. Whether a
    row was inserted is read from RETURNING, not rowcount, which the Postgres driver does not report reliably here."""
    inserted = db.execute(
        _insert(db)(ProcessedEvent)
        .values(id=new_id(), organisation_id=organisation_id, event_id=event_id, name=name)
        .on_conflict_do_nothing(index_elements=["organisation_id", "event_id"])
        .returning(ProcessedEvent.id)
    ).scalar()
    return inserted is not None


def ticket_ref(db: Session, organisation_id: str, ticket_id: str, *, create: bool) -> TicketRef | None:
    """The ticket's row, locked (FOR UPDATE on Postgres) so one ticket's events are applied one at a time. With
    create it is first inserted with ON CONFLICT DO NOTHING: FOR UPDATE locks nothing while the row does not exist,
    so of two first events at the same time the second insert waits for the first and then does nothing."""
    if create:
        db.execute(
            _insert(db)(TicketRef)
            .values(id=new_id(), organisation_id=organisation_id, ticket_id=ticket_id, created=False, final=False)
            .on_conflict_do_nothing(index_elements=["organisation_id", "ticket_id"])
        )
    query = (
        _scoped(db, TicketRef)
        .where(TicketRef.organisation_id == organisation_id, TicketRef.ticket_id == ticket_id)
        .with_for_update()
    )
    return db.scalars(query).first()


def clocks_of_ticket(db: Session, ticket_id: str) -> list[Clock]:
    """Response first, then resolution."""
    query = _scoped(db, Clock).where(Clock.ticket_id == ticket_id)
    return sorted(db.scalars(query), key=lambda c: c.kind != "response")


def escalations(db: Session, clock_id: str) -> list[Escalation]:
    query = _scoped(db, Escalation).where(Escalation.clock_id == clock_id)
    return list(db.scalars(query.order_by(Escalation.level)))


def clocks_to_check(db: Session, now: datetime, limit: int) -> list[Clock]:
    """Running clocks with a warning, breach or escalation due by `now`."""
    query = _scoped(db, Clock).where(
        Clock.state == RUNNING,
        or_(
            and_(Clock.warned.is_(False), Clock.warn_at <= now),
            and_(Clock.breached.is_(False), Clock.due_at <= now),
            Clock.next_escalation_at <= now,
        ),
    )
    return list(db.scalars(query.order_by(Clock.due_at, Clock.id).limit(limit)))


# ---------------------------------------------------------------- clock lists and statistics


def is_breached(now: datetime) -> ColumnElement[bool]:
    """Breach recorded, or a running clock past its due time (the flag follows when the clock is next checked)."""
    return or_(Clock.breached.is_(True), and_(Clock.state == RUNNING, Clock.due_at <= now))


def is_at_risk(now: datetime) -> ColumnElement[bool]:
    """Running, not breached, warning time passed (contract parameter at_risk)."""
    return and_(Clock.state == RUNNING, Clock.breached.is_(False), Clock.due_at > now, Clock.warn_at <= now)


def clock_page(
    db: Session,
    *,
    now: datetime,
    states: list[str] | None,
    kind: str | None,
    breached: bool | None,
    at_risk: bool | None,
    priority: str | None,
    category_id: str | None,
    assignee_id: str | None,
    ticket_number: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Clock], bool]:
    """Matching clocks, soonest due first (paused, stopped and cancelled ones have no due time and come last), and
    whether there are more."""
    query = _scoped(db, Clock)
    if states:
        query = query.where(Clock.state.in_(states))
    if kind is not None:
        query = query.where(Clock.kind == kind)
    if breached is not None:
        query = query.where(is_breached(now) if breached else not_(is_breached(now)))
    if at_risk is not None:
        query = query.where(is_at_risk(now) if at_risk else not_(is_at_risk(now)))
    if priority is not None:
        query = query.where(Clock.priority == priority)
    if category_id is not None:
        query = query.where(Clock.category_id == category_id)
    if assignee_id is not None:
        query = query.where(Clock.assignee_id == assignee_id)
    if ticket_number is not None:
        query = query.where(Clock.ticket_number == ticket_number)
    query = query.order_by(Clock.due_at.asc().nulls_last(), Clock.started_at, Clock.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(query))
    return rows[:limit], len(rows) > limit


def breach_counts(db: Session, *, now: datetime, since: datetime, assignee_id: str | None) -> tuple[int, int, int]:
    """(running breached, at risk, breaches in [since, now])."""
    base = _scoped(db, Clock)
    if assignee_id is not None:
        base = base.where(Clock.assignee_id == assignee_id)

    def count(*conditions) -> int:
        return db.scalar(select(func.count()).select_from(base.where(*conditions).subquery())) or 0

    recent = or_(
        and_(Clock.breached_at >= since, Clock.breached_at <= now),
        and_(Clock.breached.is_(False), Clock.state == RUNNING, Clock.due_at >= since, Clock.due_at <= now),
    )
    return (
        count(Clock.state == RUNNING, is_breached(now)),
        count(is_at_risk(now)),
        count(recent),
    )


def most_overdue(db: Session, *, now: datetime, assignee_id: str | None, limit: int) -> list[Clock]:
    """Running breached clocks, earliest due time first."""
    query = _scoped(db, Clock).where(Clock.state == RUNNING, is_breached(now))
    if assignee_id is not None:
        query = query.where(Clock.assignee_id == assignee_id)
    return list(db.scalars(query.order_by(Clock.due_at, Clock.id).limit(limit)))
