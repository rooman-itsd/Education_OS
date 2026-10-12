"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level
security enforces the same rule underneath."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import scoped
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ..domain.rules import ACTIVE_STATUSES, OpeningHours, Window
from .models import Blackout, Booking, OpeningHoursRow, Resource, ResourceType, as_utc


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def resource_for_update(db: Session, resource_id: str) -> Resource | None:
    """Lock the resource row so two requests for the same slot run one after the other (PRD section 10)."""
    return db.scalars(_scoped(db, Resource).where(Resource.id == resource_id).with_for_update()).first()


def resource_types(db: Session) -> list[ResourceType]:
    return list(db.scalars(_scoped(db, ResourceType).order_by(ResourceType.name)))


def resource_type_by_name(db: Session, name: str) -> ResourceType | None:
    return db.scalars(_scoped(db, ResourceType).where(ResourceType.name == name)).first()


def resources(db: Session) -> list[Resource]:
    return list(db.scalars(_scoped(db, Resource).order_by(Resource.name)))


def resource_by_code(db: Session, code: str) -> Resource | None:
    return db.scalars(_scoped(db, Resource).where(Resource.code == code)).first()


def count_resources_of_type(db: Session, type_id: str) -> int:
    return len(list(db.scalars(_scoped(db, Resource).where(Resource.type_id == type_id))))


def opening_hours(db: Session, resource_id: str) -> list[OpeningHoursRow]:
    q = _scoped(db, OpeningHoursRow).where(OpeningHoursRow.resource_id == resource_id)
    return list(db.scalars(q.order_by(OpeningHoursRow.weekday, OpeningHoursRow.opens)))


def opening_rules(db: Session, resource_id: str) -> list[OpeningHours]:
    return [OpeningHours(r.weekday, r.opens, r.closes) for r in opening_hours(db, resource_id)]


def blackouts(
    db: Session, resource_id: str, start: datetime | None = None, end: datetime | None = None
) -> list[Blackout]:
    q = _scoped(db, Blackout).where(Blackout.resource_id == resource_id)
    if end is not None:
        q = q.where(Blackout.start_at < end)
    if start is not None:
        q = q.where(Blackout.end_at > start)
    return list(db.scalars(q.order_by(Blackout.start_at)))


def blackout_windows(db: Session, resource_id: str, start: datetime, end: datetime) -> list[Window]:
    return [Window(as_utc(b.start_at), as_utc(b.end_at)) for b in blackouts(db, resource_id, start, end)]


def active_bookings(
    db: Session, resource_id: str, start: datetime, end: datetime, exclude_id: str | None = None
) -> list[Booking]:
    """Bookings that hold the slot (pending, confirmed, checked in) and touch [start, end)."""
    q = _scoped(db, Booking).where(
        Booking.resource_id == resource_id,
        Booking.status.in_(ACTIVE_STATUSES),
        Booking.start_at < end,
        Booking.end_at > start,
    )
    if exclude_id:
        q = q.where(Booking.id != exclude_id)
    return list(db.scalars(q.order_by(Booking.start_at)))


def bookings_between(db: Session, start: datetime | None, end: datetime | None) -> list[Booking]:
    q = _scoped(db, Booking)
    if end is not None:
        q = q.where(Booking.start_at < end)
    if start is not None:
        q = q.where(Booking.end_at > start)
    return list(db.scalars(q.order_by(Booking.start_at, Booking.id)))


def series_bookings(db: Session, series_id: str) -> list[Booking]:
    return list(db.scalars(_scoped(db, Booking).where(Booking.series_id == series_id).order_by(Booking.start_at)))


def all_unfinished_bookings(db: Session) -> list[Booking]:
    """For the scheduler sweep; the caller runs it in platform scope across organisations."""
    return list(db.scalars(select(Booking).where(Booking.status.in_(("confirmed", "checked_in")))))
