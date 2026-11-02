"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from collections.abc import Iterable

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import Assessment, Skill


def query(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(query(db, model).where(model.id == row_id)).first()


def first_by(db: Session, model, **values):
    q = query(db, model)
    for field, value in values.items():
        q = q.where(getattr(model, field) == value)
    return db.scalars(q).first()


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def skills_by_id(db: Session, ids: Iterable[str]) -> dict[str, Skill]:
    ids = set(ids)
    if not ids:
        return {}
    return {s.id: s for s in db.scalars(query(db, Skill).where(Skill.id.in_(ids)))}


def counted_assessments(
    db: Session,
    learner_id: str,
    statuses: Iterable[str],
    *,
    skill_id: str | None = None,
    framework_id: str | None = None,
) -> list[Assessment]:
    """A learner's assessments in the given statuses, oldest first, in one query (one more, for the skills, is the
    caller's). Narrowed to one skill or to the skills of one framework."""
    q = query(db, Assessment).where(Assessment.learner_id == learner_id, Assessment.status.in_(list(statuses)))
    if skill_id:
        q = q.where(Assessment.skill_id == skill_id)
    if framework_id:
        q = q.where(
            Assessment.skill_id.in_(
                query(db, Skill).with_only_columns(Skill.id).where(Skill.framework_id == framework_id)
            )
        )
    return list(db.scalars(q.order_by(Assessment.assessed_at, Assessment.created_at, Assessment.id)))
