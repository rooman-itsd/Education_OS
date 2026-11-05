"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath; on SQLite the scoping here is the only thing that does."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..domain.rules import LIVE_ROLE_STATUSES, TASK_OPEN
from .models import Production, ProductionRole, ProductionTask


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def get_for_update(db: Session, model, row_id: str):
    """Lock the row so two callers cannot both act on it (an approve/decline race, PRD rule 11).
    `key_share=True` takes the weaker FOR NO KEY UPDATE, which does not block a child row being inserted."""
    stmt = _scoped(db, model).where(model.id == row_id).with_for_update(key_share=True)
    return db.scalars(stmt.execution_options(populate_existing=True)).first()


def find_by_token(db: Session, created_by: str, client_token: str | None) -> Production | None:
    """A caller's own earlier production for this token. Never another caller's (#317's audit)."""
    if not client_token:
        return None
    stmt = _scoped(db, Production).where(Production.created_by == created_by, Production.client_token == client_token)
    return db.scalars(stmt).first()


def production_query(db: Session, filters: dict) -> Select:
    q = _scoped(db, Production)
    if statuses := filters.get("status"):
        q = q.where(Production.status.in_(tuple(statuses)))
    if kind := filters.get("kind"):
        q = q.where(Production.kind == kind)
    if department := filters.get("department"):
        q = q.where(Production.department == department)
    if start_from := filters.get("from"):
        q = q.where(Production.starts_at >= start_from)
    if start_to := filters.get("to"):
        q = q.where(Production.starts_at < start_to)
    if lead := filters.get("lead_user_id"):
        q = q.where(Production.lead_user_id == lead)
    if text := (filters.get("q") or "").strip():
        like = f"%{text.lower()}%"
        q = q.where(
            func.lower(Production.title).like(like)
            | func.lower(func.coalesce(Production.venue, "")).like(like)
            | func.lower(func.coalesce(Production.summary, "")).like(like)
        )
    return q


def count(db: Session, query: Select) -> int:
    return int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)


def page(db: Session, query: Select, page_number: int, page_size: int) -> list:
    ordered = query.order_by(Production.starts_at.is_(None), Production.starts_at, Production.created_at.desc())
    return list(db.scalars(ordered.offset((page_number - 1) * page_size).limit(page_size)))


def calendar(db: Session, statuses: tuple[str, ...], start_from: datetime, start_to: datetime | None) -> Select:
    q = _scoped(db, Production).where(Production.status.in_(statuses))
    # A production already running still belongs on the calendar, so the window is tested on the end.
    q = q.where(func.coalesce(Production.ends_at, Production.starts_at) >= start_from)
    if start_to is not None:
        q = q.where(Production.starts_at < start_to)
    return q.order_by(Production.starts_at, Production.id)


def preparing(db: Session, statuses: tuple[str, ...]) -> Select:
    q = _scoped(db, Production).where(Production.status.in_(statuses))
    return q.order_by(Production.starts_at.is_(None), Production.starts_at, Production.created_at)


def roles_of(db: Session, production_id: str) -> list[ProductionRole]:
    q = _scoped(db, ProductionRole).where(ProductionRole.production_id == production_id)
    return list(db.scalars(q.order_by(ProductionRole.created_at, ProductionRole.id)))


def live_roles_of(db: Session, production_id: str) -> list[ProductionRole]:
    q = _scoped(db, ProductionRole).where(
        ProductionRole.production_id == production_id, ProductionRole.status.in_(LIVE_ROLE_STATUSES)
    )
    return list(db.scalars(q))


def role_for(db: Session, production_id: str, user_id: str, role_name: str) -> ProductionRole | None:
    q = _scoped(db, ProductionRole).where(
        ProductionRole.production_id == production_id,
        ProductionRole.user_id == user_id,
        ProductionRole.role_name == role_name,
    )
    return db.scalars(q).first()


def roles_of_user(db: Session, user_id: str, statuses: tuple[str, ...] | None = None) -> list[ProductionRole]:
    q = _scoped(db, ProductionRole).where(ProductionRole.user_id == user_id)
    if statuses:
        q = q.where(ProductionRole.status.in_(statuses))
    return list(db.scalars(q))


def productions_by_id(db: Session, ids: set[str]) -> dict[str, Production]:
    if not ids:
        return {}
    rows = db.scalars(_scoped(db, Production).where(Production.id.in_(tuple(ids))))
    return {p.id: p for p in rows}


def tasks_of(db: Session, production_id: str) -> list[ProductionTask]:
    q = _scoped(db, ProductionTask).where(ProductionTask.production_id == production_id)
    return list(db.scalars(q.order_by(ProductionTask.status.desc(), ProductionTask.position, ProductionTask.id)))


def open_tasks_of(db: Session, production_id: str) -> list[ProductionTask]:
    q = _scoped(db, ProductionTask).where(
        ProductionTask.production_id == production_id, ProductionTask.status == TASK_OPEN
    )
    return list(db.scalars(q))


def next_position(db: Session, production_id: str) -> int:
    """Tasks keep the order they were added in. A production has a handful, so they are counted in Python
    rather than with an aggregate over a scoped subquery."""
    rows = _scoped(db, ProductionTask).where(ProductionTask.production_id == production_id)
    return max((t.position for t in db.scalars(rows)), default=0) + 1


def tasks_for(db: Session, production_ids: set[str]) -> list[ProductionTask]:
    if not production_ids:
        return []
    q = _scoped(db, ProductionTask).where(ProductionTask.production_id.in_(tuple(production_ids)))
    return list(db.scalars(q))


def roles_for(db: Session, production_ids: set[str]) -> list[ProductionRole]:
    if not production_ids:
        return []
    q = _scoped(db, ProductionRole).where(ProductionRole.production_id.in_(tuple(production_ids)))
    return list(db.scalars(q))
