"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath. The *_unscoped helpers are for the scheduler sweep, which runs in platform
scope and filters by organisation itself."""

from __future__ import annotations

from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from .models import Asset, CycleLine, DepreciationLine, DepreciationRun, Transfer


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def get_for_update(db: Session, model, row_id: str):
    """Lock the row so two requests cannot change the same asset, cycle or disposal at once."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


def all_of(db: Session, model, order_by=None) -> list:
    q = _scoped(db, model)
    if order_by is not None:
        q = q.order_by(order_by)
    return list(db.scalars(q))


def first_by(db: Session, model, field: str, value):
    return db.scalars(_scoped(db, model).where(getattr(model, field) == value)).first()


def assets(db: Session) -> list[Asset]:
    return list(db.scalars(_scoped(db, Asset).order_by(Asset.tag)))


def count_in_category(db: Session, category_id: str) -> int:
    return db.scalar(_scoped(db, Asset).with_only_columns(func.count()).where(Asset.category_id == category_id)) or 0


def transfers_of(db: Session, asset_id: str) -> list[Transfer]:
    q = _scoped(db, Transfer).where(Transfer.asset_id == asset_id).order_by(Transfer.created_at.desc(), Transfer.id)
    return list(db.scalars(q))


def lines_of(db: Session, cycle_id: str) -> list[CycleLine]:
    return list(db.scalars(_scoped(db, CycleLine).where(CycleLine.cycle_id == cycle_id).order_by(CycleLine.tag)))


def runs(db: Session) -> list[DepreciationRun]:
    return list(db.scalars(_scoped(db, DepreciationRun).order_by(DepreciationRun.period_end.desc())))


def last_posted_end(db: Session) -> date | None:
    q = _scoped(db, DepreciationRun).where(DepreciationRun.status == "posted")
    return db.scalar(q.with_only_columns(func.max(DepreciationRun.period_end)))


def run_lines(db: Session, run_id: str) -> list[DepreciationLine]:
    q = _scoped(db, DepreciationLine).where(DepreciationLine.run_id == run_id).order_by(DepreciationLine.tag)
    return list(db.scalars(q))


def posted_lines_of(db: Session, asset_id: str) -> list[tuple[DepreciationLine, DepreciationRun | None]]:
    """Depreciation already taken for an asset: lines of posted runs and the disposal catch-up."""
    q = (
        _scoped(db, DepreciationLine)
        .outerjoin(DepreciationRun, DepreciationRun.id == DepreciationLine.run_id)
        .where(DepreciationLine.asset_id == asset_id)
        .where((DepreciationLine.run_id.is_(None)) | (DepreciationRun.status == "posted"))
        .order_by(DepreciationLine.period_end)
        .add_columns(DepreciationRun)
    )
    return [(row[0], row[1]) for row in db.execute(q)]


def next_tag_number(db: Session, organisation_id: str, prefix: str) -> int:
    """Running number for generated tags, counted within the organisation. On Postgres a transaction-scoped advisory
    lock per organisation serialises two registrations that would otherwise count the same rows and collide on
    uq_asset_management_asset_tag; SQLite has one writer at a time."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"asset-management:tag:{organisation_id}"}
        )
    count = db.scalar(
        select(func.count())
        .select_from(Asset)
        .where(Asset.organisation_id == organisation_id, Asset.tag.like(f"{prefix}-%"))
    )
    return (count or 0) + 1


def assets_unscoped(db: Session) -> list[Asset]:
    return list(db.scalars(select(Asset).where(Asset.status != "disposed")))
