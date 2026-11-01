"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64

from eos_core.db import scoped
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from .models import Contract, CoveredItem, Engagement, NumberSequence


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


# ---------------------------------------------------------------- pagination (opaque cursor = offset)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(base64.urlsafe_b64decode(cursor.encode()).decode()), 0)
    except (ValueError, UnicodeDecodeError):
        return 0


def page_of(rows: list, cursor: str | None, limit: int) -> tuple[list, str | None]:
    """A page of rows already filtered in Python (expiring, expired and within_terms are worked out when read)."""
    offset = decode_cursor(cursor)
    chunk = rows[offset : offset + limit]
    return chunk, encode_cursor(offset + limit) if offset + limit < len(rows) else None


# ---------------------------------------------------------------- numbers


def next_number(db: Session, organisation_id: str, kind: str) -> int:
    """The next number of the organisation's sequence for `kind`. The row is locked (FOR UPDATE on Postgres) so two
    contracts or engagements created at the same time never get the same number; the unique (organisation_id, number)
    indexes back this."""
    q = (
        select(NumberSequence)
        .where(NumberSequence.organisation_id == organisation_id, NumberSequence.kind == kind)
        .with_for_update()
    )
    row = db.scalars(q).first()
    if row is None:
        row = NumberSequence(organisation_id=organisation_id, kind=kind, last_number=0)
        db.add(row)
    row.last_number += 1
    db.flush()
    return row.last_number


# ---------------------------------------------------------------- contracts and covered items


def contracts(
    db: Session,
    *,
    statuses: list[str] | None = None,
    vendor_id: str | None = None,
    owner_id: str | None = None,
    q: str | None = None,
) -> list[Contract]:
    """Matching contracts, soonest end date first (GET /contracts)."""
    query = _scoped(db, Contract)
    if statuses:
        query = query.where(Contract.status.in_(statuses))
    if vendor_id:
        query = query.where(Contract.vendor_id == vendor_id)
    if owner_id:
        query = query.where(Contract.owner_id == owner_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Contract.number).like(like), func.lower(Contract.title).like(like)))
    return list(db.scalars(query.order_by(Contract.end_date, Contract.number)))


def active_contracts(db: Session) -> list[Contract]:
    return list(db.scalars(_scoped(db, Contract).where(Contract.status == "active")))


def contracts_by_id(db: Session, ids: set[str]) -> dict[str, Contract]:
    if not ids:
        return {}
    return {c.id: c for c in db.scalars(_scoped(db, Contract).where(Contract.id.in_(ids)))}


def covered_items(db: Session, contract_id: str) -> list[CoveredItem]:
    query = _scoped(db, CoveredItem).where(CoveredItem.contract_id == contract_id)
    return list(db.scalars(query.order_by(CoveredItem.created_at, CoveredItem.id)))


def covered_item_with_reference(db: Session, contract_id: str, module: str, entity: str, ref_id: str):
    query = _scoped(db, CoveredItem).where(
        CoveredItem.contract_id == contract_id,
        CoveredItem.ref_module == module,
        CoveredItem.ref_entity == entity,
        CoveredItem.ref_id == ref_id,
    )
    return db.scalars(query).first()


def contract_ids_covering(db: Session, module: str, entity: str, ref_id: str) -> set[str]:
    query = _scoped(db, CoveredItem).where(
        CoveredItem.ref_module == module, CoveredItem.ref_entity == entity, CoveredItem.ref_id == ref_id
    )
    return {item.contract_id for item in db.scalars(query)}


# ---------------------------------------------------------------- engagements


def engagements(
    db: Session, *, contract_id: str | None = None, statuses: list[str] | None = None, kind: str | None = None
) -> list[Engagement]:
    """Matching engagements, newest first (GET /engagements)."""
    query = _scoped(db, Engagement)
    if contract_id:
        query = query.where(Engagement.contract_id == contract_id)
    if statuses:
        query = query.where(Engagement.status.in_(statuses))
    if kind:
        query = query.where(Engagement.kind == kind)
    return list(db.scalars(query.order_by(Engagement.reported_at.desc(), Engagement.number.desc())))
