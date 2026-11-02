"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import AthleteLink


def query(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(query(db, model).where(model.id == row_id)).first()


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def athletes_of_user(db: Session, user_id: str) -> set[str]:
    return set(
        db.scalars(
            query(db, AthleteLink).with_only_columns(AthleteLink.athlete_id).where(AthleteLink.user_id == user_id)
        )
    )


def link_of(db: Session, athlete_id: str) -> AthleteLink | None:
    return db.scalars(query(db, AthleteLink).where(AthleteLink.athlete_id == athlete_id)).first()
