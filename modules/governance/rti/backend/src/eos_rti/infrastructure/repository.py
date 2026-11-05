"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import re

from eos_core.db import scoped
from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from ..domain.requests import OPEN_STATUSES
from .models import Appeal, Referral, Response, RtiRequest, Transfer

# A cursor is the offset of the next page as plain ASCII digits; anything else is refused (422) rather than handed to
# the database. Larger offsets are refused too.
MAX_OFFSET = 10**6
CURSOR = re.compile(r"[0-9]{1,7}")


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str, *, lock: bool = False):
    """One row of the caller's organisation, or None. lock: FOR UPDATE on Postgres, so two requests changing the same
    row run one after the other and the second sees the first's result."""
    query = _scoped(db, model).where(model.id == row_id)
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


# ---------------------------------------------------------------- pagination


def decode_cursor(cursor: str | None) -> int:
    """The offset in a cursor from encode_cursor; ValueError for anything else or an offset above MAX_OFFSET."""
    if cursor is None or cursor == "":
        return 0
    if not CURSOR.fullmatch(cursor):
        raise ValueError("cursor is not an offset")
    offset = int(cursor)
    if offset > MAX_OFFSET:
        raise ValueError("cursor offset too large")
    return offset


def encode_cursor(offset: int) -> str:
    return str(offset)


def _like(value: str) -> str:
    """A LIKE pattern matching `value` anywhere, with its own % and _ taken literally."""
    escaped = value.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------------------------------------------------------------- numbering


def next_seq(db: Session, organisation_id: str) -> int:
    """The next request sequence number of the organisation. On Postgres a transaction-level advisory lock makes two
    requests recorded at once take one number after the other (SQLite runs one writer at a time); the unique
    constraint on (organisation_id, seq) backs it up."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"rti-number:{organisation_id}"}
        )
    top = db.scalar(scoped(db, select(func.max(RtiRequest.seq)), RtiRequest))
    return (top or 0) + 1


# ---------------------------------------------------------------- requests


def _request_filters(
    query: Select,
    *,
    statuses: list[str] | None,
    officer_id: str | None,
    received_via: str | None,
    q: str | None,
) -> Select:
    if statuses:
        query = query.where(RtiRequest.status.in_(statuses))
    if officer_id:
        query = query.where(RtiRequest.officer_id == officer_id)
    if received_via:
        query = query.where(RtiRequest.received_via == received_via)
    if q:
        like = _like(q)
        query = query.where(
            func.lower(RtiRequest.number).like(like, escape="\\")
            | func.lower(RtiRequest.subject).like(like, escape="\\")
        )
    return query


def requests(
    db: Session,
    *,
    statuses: list[str] | None = None,
    officer_id: str | None = None,
    received_via: str | None = None,
    q: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> list[RtiRequest]:
    """Matching requests, newest first. With offset and limit one extra row is read, so the caller can tell whether
    another page follows."""
    query = _request_filters(
        _scoped(db, RtiRequest), statuses=statuses, officer_id=officer_id, received_via=received_via, q=q
    ).order_by(RtiRequest.seq.desc())
    if limit is not None:
        query = query.offset(offset or 0).limit(limit + 1)
    return list(db.scalars(query))


def open_requests(db: Session) -> list[RtiRequest]:
    """Requests waiting for a response or an appeal decision (the ones that can be overdue)."""
    return list(db.scalars(_scoped(db, RtiRequest).where(RtiRequest.status.in_(OPEN_STATUSES))))


# ---------------------------------------------------------------- the parts of a request


def _by_request(db: Session, model, request_ids: list[str]) -> dict:
    if not request_ids:
        return {}
    return {r.request_id: r for r in db.scalars(_scoped(db, model).where(model.request_id.in_(request_ids)))}


def appeals_of(db: Session, request_ids: list[str]) -> dict[str, Appeal]:
    return _by_request(db, Appeal, request_ids)


def responses_of(db: Session, request_ids: list[str]) -> dict[str, Response]:
    return _by_request(db, Response, request_ids)


def transfers_of(db: Session, request_ids: list[str]) -> dict[str, Transfer]:
    return _by_request(db, Transfer, request_ids)


def referrals_of(db: Session, request_id: str) -> list[Referral]:
    return list(
        db.scalars(
            _scoped(db, Referral).where(Referral.request_id == request_id).order_by(Referral.created_at, Referral.id)
        )
    )


def referrals_page(
    db: Session,
    *,
    request_id: str | None = None,
    custodian_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Referral], bool]:
    """A page of matching referrals, oldest first, and whether more follow."""
    query = _scoped(db, Referral)
    if request_id:
        query = query.where(Referral.request_id == request_id)
    if custodian_id:
        query = query.where(Referral.custodian_id == custodian_id)
    if status:
        query = query.where(Referral.status == status)
    rows = list(db.scalars(query.order_by(Referral.created_at, Referral.id).offset(offset).limit(limit + 1)))
    return rows[:limit], len(rows) > limit


def numbers_of(db: Session, request_ids: set[str]) -> dict[str, str]:
    """request id -> request number."""
    if not request_ids:
        return {}
    rows = db.execute(
        scoped(db, select(RtiRequest.id, RtiRequest.number), RtiRequest).where(RtiRequest.id.in_(request_ids))
    )
    return {rid: number for rid, number in rows}
