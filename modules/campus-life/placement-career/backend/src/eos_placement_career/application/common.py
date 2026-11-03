"""What every placement-career use case shares: the clock and the Indian business date, the audit record and the
outbox, tenant-scoped queries, cursor pages, the 409 for a value taken concurrently, and the renderings several use
cases return. Authenticated calls arrive with the caller's organisation pinned on the session (api/deps), so every
query here is scoped to it."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from functools import wraps

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleError
from ..infrastructure.models import AuditEntry, Company, Drive, Opening
from .access import DRIVE_MANAGE, OPENING_MANAGE, Actor
from .errors import PlacementError, conflict, from_rule, not_found

MODULE = "placement-career"


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


# Business dates are Indian (PRD rule). Asia/Kolkata has kept UTC+05:30 without daylight saving since 1945, so a fixed
# offset is exact and needs no time-zone database (tzdata is not on the approved stack), as in e-office.
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def business_date(moment: datetime) -> date:
    """The Indian calendar date of a moment; timestamps themselves stay UTC."""
    return aware(moment).astimezone(BUSINESS_TZ).date()


def business_today() -> date:
    """Today in Asia/Kolkata: the date drive dates, last days to apply and joining dates are judged against."""
    return business_date(clock())


def publish(db: Session, name: str, organisation_id: str, payload: dict, actor: str | None = None) -> None:
    """A placement-career.* event in the outbox, in the caller's transaction. Payloads carry ids, dates and the cancel
    reason only (P9): no names, declarations, offered CTC or company contacts."""
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


def offset(cursor: str | None) -> int:
    """A cursor is the position of the next item, as this API returned it in next_cursor."""
    if cursor is None or cursor == "":
        return 0
    if not cursor.isdigit() or len(cursor) > 9:
        raise PlacementError(400, "invalid_cursor", "invalid cursor")
    return int(cursor)


def page(db: Session, query, cursor: str | None, limit: int, render) -> dict:
    """One page of an ordered query: `limit` rows from the cursor, and the cursor of the next page if there is one."""
    start = offset(cursor)
    rows = list(db.scalars(query.offset(start).limit(limit + 1)))
    more = len(rows) > limit
    return {
        "items": [render(r) for r in rows[:limit]],
        "next_cursor": str(start + limit) if more else None,
    }


def duplicate_is_409(code: str, message: str):
    """A write that takes a unique value (a company name, a student's application to an opening). When a concurrent
    request took the same value after the checks, the database refuses it at a flush or at the commit; either way the
    answer is 409, like the check before it, and nothing is kept."""

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


# ---------------------------------------------------------------- visibility


def drive_statuses(actor: Actor) -> tuple[str, ...]:
    """Draft and cancelled drives are visible only with placement-career:drive:manage."""
    return rules.DRIVE_STATUSES if actor.can(DRIVE_MANAGE) else rules.PUBLIC_DRIVE_STATUSES


def opening_statuses(actor: Actor) -> tuple[str, ...]:
    """Draft and cancelled openings are visible only with placement-career:opening:manage."""
    return rules.OPENING_STATUSES if actor.can(OPENING_MANAGE) else rules.PUBLIC_OPENING_STATUSES


def visible_drive(db: Session, actor: Actor, drive_id: str, *, lock: bool = False) -> Drive:
    query = q(db, Drive).where(Drive.id == drive_id, Drive.status.in_(drive_statuses(actor)))
    if lock:
        query = query.with_for_update()
    drive = db.scalar(query)
    if drive is None:
        raise not_found("drive")
    return drive


def visible_opening(db: Session, actor: Actor, opening_id: str, *, lock: bool = False) -> Opening:
    query = q(db, Opening).where(Opening.id == opening_id, Opening.status.in_(opening_statuses(actor)))
    if lock:
        query = query.with_for_update()
    opening = db.scalar(query)
    if opening is None:
        raise not_found("opening")
    return opening


# ---------------------------------------------------------------- renderings shared by several use cases


def company_summary(c: Company) -> dict:
    """What every reader of drives and openings sees of a company: no contact details."""
    return {"id": c.id, "name": c.name, "industry": c.industry, "website": c.website}


def companies_by_id(db: Session, ids) -> dict[str, Company]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {c.id: c for c in db.scalars(q(db, Company).where(Company.id.in_(ids)))}


def drives_by_id(db: Session, ids) -> dict[str, Drive]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {d.id: d for d in db.scalars(q(db, Drive).where(Drive.id.in_(ids)))}


def eligibility(value: dict | None) -> dict:
    """Every Eligibility property, also for a row written before a property existed."""
    value = value or {}
    return {
        "programmes": list(value.get("programmes") or []),
        "graduating_years": list(value.get("graduating_years") or []),
        "min_cgpa": value.get("min_cgpa"),
        "max_active_backlogs": value.get("max_active_backlogs"),
        "notes": value.get("notes"),
    }


def drive_brief(d: Drive | None) -> dict | None:
    """The drive as shown next to an opening, with the drive's own criteria."""
    if d is None:
        return None
    return {
        "id": d.id,
        "title": d.title,
        "scheduled_on": iso(d.scheduled_on),
        "venue": d.venue,
        "eligibility": eligibility(d.eligibility),
    }
