"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import Facility, OperatingHoursSlot, Space, UsageRecord


def query(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(query(db, model).where(model.id == row_id)).first()


def first_by(db: Session, model, **values):
    q = query(db, model)
    for field, value in values.items():
        q = q.where(getattr(model, field) == value)
    return db.scalars(q).first()


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def facilities(db: Session, facility_type: str | None, status: str | None, indoor: bool | None) -> list[Facility]:
    q = query(db, Facility)
    if facility_type:
        q = q.where(Facility.facility_type == facility_type)
    if status:
        q = q.where(Facility.status == status)
    if indoor is not None:
        q = q.where(Facility.indoor == indoor)
    return list(db.scalars(q.order_by(Facility.name, Facility.id)))


def space_of(db: Session, facility_id: str, space_id: str | None) -> Space | None:
    if not space_id:
        return None
    return db.scalars(query(db, Space).where(Space.id == space_id, Space.facility_id == facility_id)).first()


def slots(db: Session, facility_id: str) -> list[OperatingHoursSlot]:
    q = query(db, OperatingHoursSlot).where(OperatingHoursSlot.facility_id == facility_id)
    return list(db.scalars(q.order_by(OperatingHoursSlot.day_of_week, OperatingHoursSlot.opens_at)))


def usage_query(
    db: Session, facility_id: str | None, purpose: str | None, start: datetime | None, end: datetime | None
) -> Select:
    """Usage records that touch [start, end)."""
    q = query(db, UsageRecord)
    if facility_id:
        q = q.where(UsageRecord.facility_id == facility_id)
    if purpose:
        q = q.where(UsageRecord.purpose == purpose)
    if end is not None:
        q = q.where(UsageRecord.used_from < end)
    if start is not None:
        q = q.where(UsageRecord.used_to > start)
    return q


def usages(db: Session, facility_id: str, start: datetime, end: datetime) -> list[UsageRecord]:
    return list(db.scalars(usage_query(db, facility_id, None, start, end).order_by(UsageRecord.used_from)))
