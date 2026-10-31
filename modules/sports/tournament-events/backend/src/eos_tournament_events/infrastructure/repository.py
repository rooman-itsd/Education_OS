"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from collections.abc import Iterable

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import AthleteLink, Entry, Fixture


def query(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None, **values):
    if not row_id:
        return None
    q = query(db, model).where(model.id == row_id)
    for field, value in values.items():
        q = q.where(getattr(model, field) == value)
    return db.scalars(q).first()


def first_by(db: Session, model, **values):
    q = query(db, model)
    for field, value in values.items():
        q = q.where(getattr(model, field) == value)
    return db.scalars(q).first()


def all_by(db: Session, model, **values) -> list:
    q = query(db, model)
    for field, value in values.items():
        q = q.where(getattr(model, field) == value)
    return list(db.scalars(q.order_by(model.id)))


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def entries_by_id(db: Session, tournament_id: str, entry_ids: Iterable[str]) -> dict[str, Entry]:
    """The tournament's entries among entry_ids, in one query."""
    ids = set(entry_ids)
    if not ids:
        return {}
    q = query(db, Entry).where(Entry.tournament_id == tournament_id, Entry.id.in_(ids))
    return {e.id: e for e in db.scalars(q)}


def fixtures_of(db: Session, tournament_id: str, statuses: Iterable[str]) -> list[Fixture]:
    q = query(db, Fixture).where(Fixture.tournament_id == tournament_id, Fixture.status.in_(set(statuses)))
    return list(db.scalars(q.order_by(Fixture.scheduled_at, Fixture.id)))


def athletes_of_user(db: Session, user_id: str) -> set[str]:
    return set(
        db.scalars(
            query(db, AthleteLink).with_only_columns(AthleteLink.athlete_id).where(AthleteLink.user_id == user_id)
        )
    )


def link_of(db: Session, athlete_id: str) -> AthleteLink | None:
    return first_by(db, AthleteLink, athlete_id=athlete_id)
