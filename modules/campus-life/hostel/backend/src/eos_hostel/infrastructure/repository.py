"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date, datetime

from eos_core.db import scoped
from sqlalchemy import Select, and_, not_, or_, select
from sqlalchemy.orm import Session

from ..domain.rules import BED_HOLDING, LEAVE_AWAY, LEAVE_BLOCKING, OPEN_FOR_YEAR
from .models import Allocation, Hostel, Incident, LeaveRequest, MessMenu, Notice, Room, Visit


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def room_for_update(db: Session, room_id: str) -> Room | None:
    """Lock the room so two allocations to it run one after the other and capacity is never exceeded."""
    return db.scalars(_scoped(db, Room).where(Room.id == room_id).with_for_update()).first()


# ---------------------------------------------------------------- pagination

MAX_LIMIT = 100


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(base64.urlsafe_b64decode(cursor.encode()).decode()), 0)
    except (ValueError, UnicodeDecodeError):
        return 0


def page(db: Session, query: Select, cursor: str | None, limit: int) -> tuple[list, str | None]:
    offset = decode_cursor(cursor)
    rows = list(db.scalars(query.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    return rows[:limit], encode_cursor(offset + limit) if more else None


# ---------------------------------------------------------------- hostels and rooms


def hostels(db: Session, active: bool | None = None) -> list[Hostel]:
    q = _scoped(db, Hostel)
    if active is not None:
        q = q.where(Hostel.active.is_(active))
    return list(db.scalars(q.order_by(Hostel.name, Hostel.id)))


def rooms(db: Session, hostel_id: str, status: str | None = None) -> list[Room]:
    q = _scoped(db, Room).where(Room.hostel_id == hostel_id)
    if status:
        q = q.where(Room.status == status)
    return list(db.scalars(q.order_by(Room.number, Room.id)))


def room_by_number(db: Session, hostel_id: str, number: str) -> Room | None:
    return db.scalars(_scoped(db, Room).where(Room.hostel_id == hostel_id, Room.number == number)).first()


def holding_allocations(db: Session, room_ids: list[str], on: date | None = None) -> list[Allocation]:
    """Allocations that hold a bed in these rooms (confirmed or occupied), optionally only those covering `on`.
    An occupied allocation holds its bed until check-out, whatever its planned to_date says."""
    if not room_ids:
        return []
    q = _scoped(db, Allocation).where(Allocation.room_id.in_(room_ids), Allocation.status.in_(BED_HOLDING))
    if on is not None:
        q = q.where(or_(Allocation.status == "occupied", Allocation.to_date.is_(None), Allocation.to_date >= on))
    return list(db.scalars(q))


# ---------------------------------------------------------------- allocations


def allocations_query(
    db: Session,
    status: str | None = None,
    hostel_id: str | None = None,
    academic_year: str | None = None,
    person_id: str | None = None,
) -> Select:
    q = _scoped(db, Allocation)
    if status:
        q = q.where(Allocation.status == status)
    if hostel_id:
        q = q.where(or_(Allocation.hostel_id == hostel_id, Allocation.preferred_hostel_id == hostel_id))
    if academic_year:
        q = q.where(Allocation.academic_year == academic_year)
    if person_id:
        q = q.where(Allocation.person_id == person_id)
    return q.order_by(Allocation.created_at.desc(), Allocation.id)


def open_for_year(db: Session, person_id: str, academic_year: str) -> Allocation | None:
    q = _scoped(db, Allocation).where(
        Allocation.person_id == person_id,
        Allocation.academic_year == academic_year,
        Allocation.status.in_(OPEN_FOR_YEAR),
    )
    return db.scalars(q).first()


def person_holding(db: Session, person_id: str, exclude_id: str | None = None) -> list[Allocation]:
    q = _scoped(db, Allocation).where(Allocation.person_id == person_id, Allocation.status.in_(BED_HOLDING))
    if exclude_id:
        q = q.where(Allocation.id != exclude_id)
    return list(db.scalars(q))


def person_allocations(db: Session, person_id: str) -> list[Allocation]:
    q = _scoped(db, Allocation).where(Allocation.person_id == person_id)
    return list(db.scalars(q.order_by(Allocation.created_at.desc(), Allocation.id)))


def occupied_allocation(db: Session, person_id: str) -> Allocation | None:
    """The person's checked-in allocation: what makes them a current resident."""
    q = _scoped(db, Allocation).where(Allocation.person_id == person_id, Allocation.status == "occupied")
    return db.scalars(q.order_by(Allocation.checked_in_at.desc())).first()


# ---------------------------------------------------------------- mess menu


def menu_row(db: Session, hostel_id: str, menu_date: date, meal: str) -> MessMenu | None:
    q = _scoped(db, MessMenu).where(
        MessMenu.hostel_id == hostel_id, MessMenu.menu_date == menu_date, MessMenu.meal == meal
    )
    return db.scalars(q).first()


def menus(db: Session, hostel_id: str, start: date, end: date) -> list[MessMenu]:
    q = _scoped(db, MessMenu).where(
        MessMenu.hostel_id == hostel_id, MessMenu.menu_date >= start, MessMenu.menu_date <= end
    )
    return list(db.scalars(q.order_by(MessMenu.menu_date, MessMenu.meal)))


# ---------------------------------------------------------------- leave


def leave_query(
    db: Session,
    now: datetime,
    status: str | None = None,
    hostel_id: str | None = None,
    overdue: bool | None = None,
    statuses: tuple[str, ...] | None = None,
) -> Select:
    """overdue=True: approved or out leave whose end has passed without a return; overdue=False: everything else.
    `statuses` limits the result to those statuses (the security desk sees only gate-pass statuses)."""
    q = _scoped(db, LeaveRequest)
    if status:
        q = q.where(LeaveRequest.status == status)
    if statuses:
        q = q.where(LeaveRequest.status.in_(statuses))
    if hostel_id:
        q = q.where(LeaveRequest.hostel_id == hostel_id)
    is_overdue = and_(LeaveRequest.status.in_(LEAVE_AWAY), LeaveRequest.to_at < now)
    if overdue is True:
        q = q.where(is_overdue)
    elif overdue is False:
        q = q.where(not_(is_overdue))
    return q.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id)


def blocking_leave(db: Session, person_id: str) -> list[LeaveRequest]:
    q = _scoped(db, LeaveRequest).where(LeaveRequest.person_id == person_id, LeaveRequest.status.in_(LEAVE_BLOCKING))
    return list(db.scalars(q))


def person_leave(db: Session, person_id: str) -> list[LeaveRequest]:
    q = _scoped(db, LeaveRequest).where(LeaveRequest.person_id == person_id)
    return list(db.scalars(q.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id)))


def unflagged_overdue_leave(db: Session, before: datetime) -> list[LeaveRequest]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    q = select(LeaveRequest).where(
        LeaveRequest.status.in_(LEAVE_AWAY), LeaveRequest.to_at < before, LeaveRequest.overdue_flagged_at.is_(None)
    )
    return list(db.scalars(q))


# ---------------------------------------------------------------- visits


def visits_query(db: Session, hostel_id: str | None = None, person_id: str | None = None) -> Select:
    q = _scoped(db, Visit)
    if hostel_id:
        q = q.where(Visit.hostel_id == hostel_id)
    if person_id:
        q = q.where(Visit.person_id == person_id)
    return q.order_by(Visit.in_at.desc(), Visit.id)


def person_visits(db: Session, person_id: str) -> list[Visit]:
    return list(db.scalars(visits_query(db, person_id=person_id)))


# ---------------------------------------------------------------- incidents


def incidents_query(
    db: Session, hostel_id: str | None = None, person_id: str | None = None, status: str | None = None
) -> Select:
    q = _scoped(db, Incident)
    if hostel_id:
        q = q.where(Incident.hostel_id == hostel_id)
    if person_id:
        q = q.where(Incident.person_id == person_id)
    if status:
        q = q.where(Incident.status == status)
    return q.order_by(Incident.occurred_at.desc(), Incident.id)


# ---------------------------------------------------------------- notices


def notices(db: Session, hostel_id: str | None = None) -> list[Notice]:
    q = _scoped(db, Notice)
    if hostel_id:
        q = q.where(Notice.hostel_id == hostel_id)
    return list(db.scalars(q.order_by(Notice.published_at.desc(), Notice.id)))


def candidate_notices_for(db: Session, hostel_id: str | None) -> list[Notice]:
    """Not withdrawn, for every hostel or this one, newest first. Expiry is checked by the caller."""
    target = (
        Notice.hostel_id.is_(None)
        if hostel_id is None
        else or_(Notice.hostel_id.is_(None), Notice.hostel_id == hostel_id)
    )
    q = _scoped(db, Notice).where(Notice.withdrawn_at.is_(None), target)
    return list(db.scalars(q.order_by(Notice.published_at.desc(), Notice.id)))
