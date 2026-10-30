"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from collections.abc import Iterable

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import Assessment, AuditEntry, Benchmark, Clearance, Result


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


def ids_present(db: Session, model, ids: Iterable[str]) -> set[str]:
    ids = set(ids)
    if not ids:
        return set()
    return set(db.scalars(query(db, model).with_only_columns(model.id).where(model.id.in_(ids))))


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def results_of(db: Session, athlete_ids: Iterable[str], metric_id: str | None = None) -> list[Result]:
    q = query(db, Result).where(Result.athlete_id.in_(set(athlete_ids)))
    if metric_id:
        q = q.where(Result.metric_id == metric_id)
    return list(db.scalars(q.order_by(Result.recorded_at, Result.id)))


def assessments_of(db: Session, athlete_ids: Iterable[str]) -> list[Assessment]:
    q = query(db, Assessment).where(Assessment.athlete_id.in_(set(athlete_ids)))
    return list(db.scalars(q.order_by(Assessment.assessed_on, Assessment.created_at, Assessment.id)))


def benchmarks_for(db: Session, metric_ids: Iterable[str] | None = None) -> list[Benchmark]:
    q = query(db, Benchmark)
    if metric_ids is not None:
        q = q.where(Benchmark.metric_id.in_(set(metric_ids)))
    return list(db.scalars(q.order_by(Benchmark.created_at, Benchmark.id)))


def clearances_of(db: Session, athlete_ids: Iterable[str]) -> dict[str, Clearance]:
    q = query(db, Clearance).where(Clearance.athlete_id.in_(set(athlete_ids)))
    return {c.athlete_id: c for c in db.scalars(q)}


def audit_entry_by_token(db: Session, organisation_id: str, token: str) -> AuditEntry | None:
    q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id, AuditEntry.client_token == token)
    return db.scalars(q).first()
