"""The joinings-and-exits report behind the HR Staff widget."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..infrastructure.models import Employee
from . import common
from .common import iso, q
from .errors import invalid

RECENT = 10


def _entry(e: Employee, day: date) -> dict:
    return {
        "employee_id": e.id,
        "name": e.name,
        "designation": e.designation,
        "department_name": e.department_name,
        "date": iso(day),
    }


def joinings_and_exits(db: Session, start: date | None, end: date | None) -> dict:
    """Joinings and exits between two dates (default: the first of this month to today, Indian dates), the headcount
    on the end date, the ten most recent of each, and the employees on notice by last working day."""
    today = common.business_today()
    end = end or today
    start = start or end.replace(day=1)
    if start > end:
        raise invalid("invalid_range", "from cannot be after to", "from")
    everyone = list(db.scalars(q(db, Employee)))
    joined = sorted(
        (e for e in everyone if start <= e.joined_on <= end), key=lambda e: (e.joined_on, e.name), reverse=True
    )
    exited = sorted(
        (
            e
            for e in everyone
            if e.exit_last_working_day is not None
            and start <= e.exit_last_working_day <= end
            and e.exit_last_working_day <= today
        ),
        key=lambda e: (e.exit_last_working_day, e.name),
        reverse=True,
    )
    headcount = sum(
        1
        for e in everyone
        if e.joined_on <= end and (e.exit_last_working_day is None or e.exit_last_working_day >= end)
    )
    on_notice = sorted(
        (e for e in everyone if e.status == "on_notice"), key=lambda e: (e.exit_last_working_day, e.name)
    )
    return {
        "from": iso(start),
        "to": iso(end),
        "joined": len(joined),
        "exited": len(exited),
        "headcount": headcount,
        "recent_joinings": [_entry(e, e.joined_on) for e in joined[:RECENT]],
        "recent_exits": [_entry(e, e.exit_last_working_day) for e in exited[:RECENT]],
        "upcoming_exits": [_entry(e, e.exit_last_working_day) for e in on_notice[:RECENT]],
    }
