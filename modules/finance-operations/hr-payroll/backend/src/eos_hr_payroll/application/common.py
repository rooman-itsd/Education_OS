"""What every hr-payroll use case shares: the clock and the Indian business date, the audit record and the outbox,
tenant-scoped queries, paging and the 409 for a value taken concurrently. Authenticated calls arrive with the caller's
organisation pinned on the session (api/deps), so every query here is scoped to it."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from functools import wraps

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.rules import RuleError
from ..infrastructure.models import AuditEntry, Employee
from .access import Actor
from .errors import HrPayrollError, conflict, from_rule, not_found

MODULE = "hr-payroll"


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


# Business dates follow the Indian calendar (as procurement; decided by the owner on #335). Asia/Kolkata has kept UTC+05:30 without
# daylight saving since 1945, so a fixed offset is exact and needs no time-zone database (tzdata is not approved).
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def business_date(moment: datetime) -> date:
    """The Indian calendar date of a moment; timestamps themselves stay UTC."""
    return aware(moment).astimezone(BUSINESS_TZ).date()


def business_today() -> date:
    """Today in Asia/Kolkata: the date "in the past", "on notice" and "late" are judged against."""
    return business_date(clock())


def publish(db: Session, name: str, organisation_id: str, payload: dict, actor: str | None = None) -> None:
    """An hr-payroll.* event in the outbox, in the caller's transaction. Payloads carry ids, dates and names only:
    never an individual's salary, bank account or PAN."""
    events.publish(
        db, f"{MODULE}.{name}", organisation_id, {"organisation_id": organisation_id, **payload}, actor=actor
    )


def audit(db: Session, actor_id: str | None, action: str, entity: str, row) -> None:
    """One audit record per state change, in the same transaction. The row is flushed first so a new one has its id."""
    db.flush()
    db.add(
        AuditEntry(
            organisation_id=row.organisation_id,
            actor=actor_id,
            action=action,
            entity=entity,
            entity_id=row.id,
            occurred_at=clock(),
        )
    )


def rule(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RuleError as e:
        raise from_rule(e) from e


def q(db: Session, model):
    return scoped(db, select(model), model)


def count(db: Session, model):
    """SELECT count(*) of a model, scoped to the caller's organisation."""
    return scoped(db, select(func.count()).select_from(model), model)


def get(db: Session, model, row_id: str, what: str, *, lock: bool = False):
    query = q(db, model).where(model.id == row_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise not_found(what)
    return row


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = aware(value)
    return value.isoformat()


def text(value: str | None) -> str:
    return (value or "").strip()


def offset(cursor: str | None) -> int:
    try:
        value = int(cursor) if cursor else 0
    except ValueError as e:
        raise HrPayrollError(400, "invalid_cursor", "invalid cursor") from e
    if value < 0:
        raise HrPayrollError(400, "invalid_cursor", "invalid cursor")
    return value


def page(rows: list, cursor: str | None, limit: int, render) -> dict:
    start = offset(cursor)
    chunk = rows[start : start + limit]
    return {
        "items": [render(r) for r in chunk],
        "next_cursor": str(start + limit) if len(rows) > start + limit else None,
    }


def duplicate_is_409(code: str, message: str):
    """A write that takes a unique value (an employee code, a linked user, a leave type code, a month's run, an
    appraisal per cycle). When a concurrent request took the same value after the checks, the database refuses it at a
    flush or at the commit; either way the answer is 409, like the check before it, and nothing is kept."""

    def wrap(fn):
        @wraps(fn)
        def run(db: Session, *args, **kwargs):
            try:
                return fn(db, *args, **kwargs)
            except IntegrityError as e:
                db.rollback()
                raise conflict(code, message) from e

        return run

    return wrap


def own_employee(db: Session, actor: Actor) -> Employee | None:
    """The caller's employee record in their organisation, through the platform/identity user it is linked to."""
    return db.scalar(q(db, Employee).where(Employee.user_id == actor.user_id))


def require_own_employee(db: Session, actor: Actor) -> Employee:
    e = own_employee(db, actor)
    if e is None:
        raise HrPayrollError(404, "not_an_employee", "you are not an employee of this organisation")
    return e


def is_self(actor: Actor, employee: Employee) -> bool:
    return bool(employee.user_id) and employee.user_id == actor.user_id
