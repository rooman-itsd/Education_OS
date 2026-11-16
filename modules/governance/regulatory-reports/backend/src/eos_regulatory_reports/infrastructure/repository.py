"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64
import binascii
from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, and_, func, not_, or_, select
from sqlalchemy.orm import Session

from ..domain.filings import NOT_SUBMITTED
from .models import Filing, Obligation

# An opaque cursor is an offset. Larger offsets, and anything that does not decode, are refused (422) rather than
# handed to the database.
MAX_OFFSET = 10**6
MAX_CURSOR_LEN = 16


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str, *, lock: bool = False):
    """One row of the caller's organisation, or None. lock: FOR UPDATE on Postgres, so two requests changing the same
    row run one after the other and the second sees the first's result."""
    query = _scoped(db, model).where(model.id == row_id)
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


# ---------------------------------------------------------------- pagination (opaque cursor = offset)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """The offset in a cursor from encode_cursor; ValueError for anything else or an offset above MAX_OFFSET."""
    if not cursor:
        return 0
    if len(cursor) > MAX_CURSOR_LEN:
        raise ValueError("cursor too long")
    try:
        text = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    except (binascii.Error, UnicodeError) as e:
        raise ValueError("cursor does not decode") from e
    if not text.isdigit():
        raise ValueError("cursor is not an offset")
    offset = int(text)
    if offset > MAX_OFFSET:
        raise ValueError("cursor offset too large")
    return offset


def _like(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, with its own % and _ taken literally."""
    escaped = text.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------------------------------------------------------------- obligations


def obligations(
    db: Session,
    *,
    authority: str | None = None,
    active: bool | None = None,
    q: str | None = None,
    only_ids: set[str] | None = None,
) -> list[Obligation]:
    """Matching obligations by title (GET /obligations). authority matches the whole label, ignoring case; q matches
    part of the title or the authority. only_ids limits the list (a preparer sees the obligations of their filings)."""
    query = _scoped(db, Obligation)
    if only_ids is not None:
        if not only_ids:
            return []
        query = query.where(Obligation.id.in_(only_ids))
    if authority:
        query = query.where(func.lower(Obligation.authority) == authority.lower())
    if active is not None:
        query = query.where(Obligation.active.is_(active))
    if q:
        like = _like(q)
        query = query.where(
            or_(
                func.lower(Obligation.title).like(like, escape="\\"),
                func.lower(Obligation.authority).like(like, escape="\\"),
            )
        )
    return list(db.scalars(query.order_by(Obligation.title, Obligation.id)))


def obligations_by_id(db: Session, ids: set[str]) -> dict[str, Obligation]:
    if not ids:
        return {}
    return {o.id: o for o in db.scalars(_scoped(db, Obligation).where(Obligation.id.in_(ids)))}


def obligation_ids_owned_by(db: Session, owner_id: str) -> set[str]:
    query = scoped(db, select(Filing.obligation_id), Filing).where(Filing.owner_id == owner_id).distinct()
    return set(db.scalars(query))


def filing_counts(db: Session, obligation_id: str, owner_id: str | None = None) -> dict[str, int]:
    """status -> number of filings of the obligation (only those of owner_id when given)."""
    query = scoped(db, select(Filing.status, func.count()), Filing).where(Filing.obligation_id == obligation_id)
    if owner_id is not None:
        query = query.where(Filing.owner_id == owner_id)
    return {status: count for status, count in db.execute(query.group_by(Filing.status))}


# ---------------------------------------------------------------- filings


def _overdue(today: date):
    return and_(Filing.status.in_(NOT_SUBMITTED), Filing.due_on < today)


def filings_page(
    db: Session,
    *,
    today: date,
    obligation_id: str | None = None,
    statuses: list[str] | None = None,
    owner_id: str | None = None,
    overdue: bool | None = None,
    due_before: date | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Filing], bool]:
    """A page of matching filings, soonest due first, and whether more follow (GET /filings). due_before excludes the
    day itself."""
    query = _scoped(db, Filing)
    if obligation_id:
        query = query.where(Filing.obligation_id == obligation_id)
    if statuses:
        query = query.where(Filing.status.in_(statuses))
    if owner_id:
        query = query.where(Filing.owner_id == owner_id)
    if overdue is True:
        query = query.where(_overdue(today))
    elif overdue is False:
        query = query.where(not_(_overdue(today)))
    if due_before is not None:
        query = query.where(Filing.due_on < due_before)
    query = query.order_by(Filing.due_on, Filing.period_label, Filing.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(query))
    return rows[:limit], len(rows) > limit


def open_filings_due_by(db: Session, cutoff: date, owner_id: str | None = None) -> list[Filing]:
    """Filings not yet submitted that are due on or before cutoff (GET /stats/due): the overdue and due-soon
    candidates."""
    query = _scoped(db, Filing).where(Filing.status.in_(NOT_SUBMITTED), Filing.due_on <= cutoff)
    if owner_id is not None:
        query = query.where(Filing.owner_id == owner_id)
    return list(db.scalars(query))


def filings_due_between(db: Session, start: date, end: date) -> list[Filing]:
    """Filings of any status due from start to end, both included (GET /calendar)."""
    query = _scoped(db, Filing).where(Filing.due_on >= start, Filing.due_on <= end)
    return list(db.scalars(query))


def filing_with_label(db: Session, obligation_id: str, period_label: str) -> Filing | None:
    query = _scoped(db, Filing).where(Filing.obligation_id == obligation_id, Filing.period_label == period_label)
    return db.scalars(query).first()
