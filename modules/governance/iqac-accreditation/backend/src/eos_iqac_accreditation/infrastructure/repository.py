"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64
import binascii
from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, and_, func, not_, select
from sqlalchemy.orm import Session

from ..domain import accreditation as rules
from .models import ActionItem, Cycle, Evidence, Framework, Metric, Response

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
    if not (text.isascii() and text.isdigit()):
        raise ValueError("cursor is not an offset")
    offset = int(text)
    if offset > MAX_OFFSET:
        raise ValueError("cursor offset too large")
    return offset


# ---------------------------------------------------------------- frameworks and metrics


def frameworks(db: Session, active: bool | None = None) -> list[Framework]:
    query = _scoped(db, Framework)
    if active is not None:
        query = query.where(Framework.active.is_(active))
    return list(db.scalars(query.order_by(Framework.code, Framework.id)))


def framework_with_code(db: Session, code: str) -> Framework | None:
    return db.scalars(_scoped(db, Framework).where(Framework.code == code)).first()


def frameworks_by_id(db: Session, ids: set[str]) -> dict[str, Framework]:
    if not ids:
        return {}
    return {f.id: f for f in db.scalars(_scoped(db, Framework).where(Framework.id.in_(ids)))}


def metrics(
    db: Session, framework_id: str, *, criterion: str | None = None, active: bool | None = None
) -> list[Metric]:
    """Metrics of a framework by code. criterion matches the whole label, ignoring case."""
    query = _scoped(db, Metric).where(Metric.framework_id == framework_id)
    if criterion:
        query = query.where(func.lower(Metric.criterion) == criterion.lower())
    if active is not None:
        query = query.where(Metric.active.is_(active))
    return list(db.scalars(query.order_by(Metric.code, Metric.id)))


def metric_with_code(db: Session, framework_id: str, code: str) -> Metric | None:
    query = _scoped(db, Metric).where(Metric.framework_id == framework_id, Metric.code == code)
    return db.scalars(query).first()


def metrics_by_id(db: Session, ids: set[str]) -> dict[str, Metric]:
    if not ids:
        return {}
    return {m.id: m for m in db.scalars(_scoped(db, Metric).where(Metric.id.in_(ids)))}


# ---------------------------------------------------------------- cycles


def framework_in_open_cycle(db: Session, framework_id: str) -> bool:
    query = _scoped(db, Cycle).where(Cycle.framework_id == framework_id, Cycle.status.in_(rules.OPEN_CYCLE)).limit(1)
    return db.scalars(query).first() is not None


def cycles(db: Session, *, framework_id: str | None = None, status: str | None = None) -> list[Cycle]:
    """Newest first."""
    query = _scoped(db, Cycle)
    if framework_id:
        query = query.where(Cycle.framework_id == framework_id)
    if status:
        query = query.where(Cycle.status == status)
    return list(db.scalars(query.order_by(Cycle.created_at.desc(), Cycle.id)))


def response_counts(db: Session, cycle_id: str, today: date) -> dict[str, int]:
    """Responses of the cycle by status, and how many of them are overdue (zeros included)."""
    counts = dict.fromkeys(rules.RESPONSE_STATUSES, 0)
    query = scoped(db, select(Response.status, func.count()), Response).where(Response.cycle_id == cycle_id)
    for status, count in db.execute(query.group_by(Response.status)):
        counts[status] = count
    overdue = scoped(db, select(func.count()), Response).where(Response.cycle_id == cycle_id, _overdue(today))
    return {**counts, "overdue": db.scalar(overdue) or 0}


def has_unaccepted_response(db: Session, cycle_id: str) -> bool:
    query = _scoped(db, Response).where(Response.cycle_id == cycle_id, Response.status != rules.ACCEPTED).limit(1)
    return db.scalars(query).first() is not None


# ---------------------------------------------------------------- responses


def _overdue(today: date):
    return and_(Response.status.in_(rules.AWAITING_OWNER), Response.due_on < today)


def assigned_metric_ids(db: Session, cycle_id: str) -> set[str]:
    return set(db.scalars(scoped(db, select(Response.metric_id), Response).where(Response.cycle_id == cycle_id)))


def responses_page(
    db: Session,
    *,
    today: date,
    cycle_id: str | None = None,
    owner_id: str | None = None,
    status: str | None = None,
    overdue: bool | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Response], bool]:
    """A page of matching responses, soonest due first, and whether more follow (GET /responses)."""
    query = _scoped(db, Response)
    if cycle_id:
        query = query.where(Response.cycle_id == cycle_id)
    if owner_id:
        query = query.where(Response.owner_id == owner_id)
    if status:
        query = query.where(Response.status == status)
    if overdue is True:
        query = query.where(_overdue(today))
    elif overdue is False:
        query = query.where(not_(_overdue(today)))
    query = query.order_by(Response.due_on, Response.created_at, Response.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(query))
    return rows[:limit], len(rows) > limit


def evidence_of(db: Session, response_ids: list[str]) -> dict[str, list[Evidence]]:
    """Evidence of each response, oldest first."""
    out: dict[str, list[Evidence]] = {rid: [] for rid in response_ids}
    if not response_ids:
        return out
    query = _scoped(db, Evidence).where(Evidence.response_id.in_(response_ids)).order_by(Evidence.added_at, Evidence.id)
    for e in db.scalars(query):
        out[e.response_id].append(e)
    return out


def evidence_of_response(db: Session, response_id: str, evidence_id: str, *, lock: bool = False) -> Evidence | None:
    query = _scoped(db, Evidence).where(Evidence.id == evidence_id, Evidence.response_id == response_id)
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


# ---------------------------------------------------------------- action items


def _action_overdue(today: date):
    return and_(ActionItem.status.in_(rules.ACTION_LIVE), ActionItem.due_on < today)


def action_items_page(
    db: Session,
    *,
    today: date,
    status: str | None = None,
    owner_id: str | None = None,
    cycle_id: str | None = None,
    overdue: bool | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[ActionItem], bool]:
    """A page of matching action items, soonest due first, and whether more follow (GET /action-items)."""
    query = _scoped(db, ActionItem)
    if status:
        query = query.where(ActionItem.status == status)
    if owner_id:
        query = query.where(ActionItem.owner_id == owner_id)
    if cycle_id:
        query = query.where(ActionItem.cycle_id == cycle_id)
    if overdue is True:
        query = query.where(_action_overdue(today))
    elif overdue is False:
        query = query.where(not_(_action_overdue(today)))
    query = query.order_by(ActionItem.due_on, ActionItem.created_at, ActionItem.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(query))
    return rows[:limit], len(rows) > limit


def action_item_counts(db: Session, today: date, due_soon_until: date) -> dict[str, int]:
    """Counts behind GET /stats/action-items: open, in progress, overdue, and due from today to due_soon_until."""
    live = scoped(db, select(ActionItem.status, func.count()), ActionItem).where(
        ActionItem.status.in_(rules.ACTION_LIVE)
    )
    counts = dict.fromkeys(rules.ACTION_LIVE, 0)
    for status, count in db.execute(live.group_by(ActionItem.status)):
        counts[status] = count
    overdue = scoped(db, select(func.count()), ActionItem).where(_action_overdue(today))
    soon = scoped(db, select(func.count()), ActionItem).where(
        ActionItem.status.in_(rules.ACTION_LIVE), ActionItem.due_on >= today, ActionItem.due_on <= due_soon_until
    )
    return {
        "open": counts[rules.OPEN],
        "in_progress": counts[rules.IN_PROGRESS],
        "overdue": db.scalar(overdue) or 0,
        "due_soon": db.scalar(soon) or 0,
    }


def soonest_action_items(db: Session, limit: int = 10) -> list[ActionItem]:
    query = _scoped(db, ActionItem).where(ActionItem.status.in_(rules.ACTION_LIVE))
    return list(db.scalars(query.order_by(ActionItem.due_on, ActionItem.created_at, ActionItem.id).limit(limit)))
