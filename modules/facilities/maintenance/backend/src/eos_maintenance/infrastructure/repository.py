"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath. The *_unscoped helpers are for the scheduler sweeps, which run in platform
scope and filter by organisation themselves."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from ..domain.rules import OPEN_STATUSES
from .models import Schedule, Ticket, WorkEntry


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def get_for_update(db: Session, model, row_id: str):
    """Lock the row so two people cannot move the same ticket at once."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


def all_of(db: Session, model, order_by=None) -> list:
    q = _scoped(db, model)
    if order_by is not None:
        q = q.order_by(order_by)
    return list(db.scalars(q))


def first_by(db: Session, model, field: str, value):
    return db.scalars(_scoped(db, model).where(getattr(model, field) == value)).first()


def tickets(db: Session) -> list[Ticket]:
    return list(db.scalars(_scoped(db, Ticket).order_by(Ticket.created_at, Ticket.id)))


def open_tickets_in_category(db: Session, category_id: str) -> list[Ticket]:
    q = _scoped(db, Ticket).where(Ticket.category_id == category_id, Ticket.status.in_(OPEN_STATUSES))
    return list(db.scalars(q))


def tickets_of_schedule(db: Session, schedule_id: str, limit: int = 5) -> list[Ticket]:
    q = _scoped(db, Ticket).where(Ticket.schedule_id == schedule_id).order_by(Ticket.created_at.desc()).limit(limit)
    return list(db.scalars(q))


def entries_of(db: Session, ticket_id: str) -> list[WorkEntry]:
    q = _scoped(db, WorkEntry).where(WorkEntry.ticket_id == ticket_id).order_by(WorkEntry.position, WorkEntry.id)
    return list(db.scalars(q))


def next_position(db: Session, ticket_id: str) -> int:
    last = db.scalar(select(func.max(WorkEntry.position)).where(WorkEntry.ticket_id == ticket_id))
    return (last or 0) + 1


def schedules(db: Session) -> list[Schedule]:
    return list(db.scalars(_scoped(db, Schedule).order_by(Schedule.next_due_on, Schedule.id)))


def next_number(db: Session, organisation_id: str, year: int) -> str:
    """MT-<year>-<sequence>, counted within the organisation. Filters by organisation explicitly so the scheduler
    sweep, which runs in platform scope, numbers each organisation's tickets on their own. On Postgres a
    transaction-scoped advisory lock per organisation serialises two raises that would otherwise count the same
    rows and collide on uq_maintenance_ticket_number; SQLite has one writer at a time."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"maintenance:number:{organisation_id}"}
        )
    prefix = f"MT-{year}-"
    count = db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.organisation_id == organisation_id, Ticket.number.like(f"{prefix}%"))
    )
    return f"{prefix}{(count or 0) + 1:05d}"


def tickets_unscoped(db: Session, statuses: tuple[str, ...]) -> list[Ticket]:
    return list(db.scalars(select(Ticket).where(Ticket.status.in_(statuses))))


def active_schedules_unscoped(db: Session) -> list[Schedule]:
    return list(db.scalars(select(Schedule).where(Schedule.active.is_(True))))


def ticket_unscoped(db: Session, ticket_id: str | None) -> Ticket | None:
    if not ticket_id:
        return None
    return db.get(Ticket, ticket_id)
