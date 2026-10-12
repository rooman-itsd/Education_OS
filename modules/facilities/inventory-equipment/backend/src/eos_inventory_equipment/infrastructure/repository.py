"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ..domain.rules import OPEN_LOAN_STATUSES, OUT_LOAN_STATUSES
from .models import Loan, LoanLine, Movement, StockLevel, Unit


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def get_for_update(db: Session, model, row_id: str):
    """Lock the row so two requests cannot both take the last item (PRD section 10)."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


def all_of(db: Session, model, order_by=None) -> list:
    q = _scoped(db, model)
    if order_by is not None:
        q = q.order_by(order_by)
    return list(db.scalars(q))


def by_field(db: Session, model, field: str, value) -> list:
    return list(db.scalars(_scoped(db, model).where(getattr(model, field) == value)))


def first_by(db: Session, model, field: str, value):
    return db.scalars(_scoped(db, model).where(getattr(model, field) == value)).first()


def stock_level(db: Session, item_id: str, location_id: str, *, lock: bool = False) -> StockLevel | None:
    q = _scoped(db, StockLevel).where(StockLevel.item_id == item_id, StockLevel.location_id == location_id)
    if lock:
        q = q.with_for_update()
    return db.scalars(q).first()


def stock_levels(db: Session, item_id: str | None = None, location_id: str | None = None) -> list[StockLevel]:
    q = _scoped(db, StockLevel)
    if item_id:
        q = q.where(StockLevel.item_id == item_id)
    if location_id:
        q = q.where(StockLevel.location_id == location_id)
    return list(db.scalars(q))


def units_of(db: Session, item_id: str) -> list[Unit]:
    return list(db.scalars(_scoped(db, Unit).where(Unit.item_id == item_id).order_by(Unit.tag)))


def movements(db: Session) -> list[Movement]:
    return list(db.scalars(_scoped(db, Movement).order_by(Movement.created_at.desc(), Movement.id)))


def item_has_stock_history(db: Session, item_id: str) -> bool:
    return bool(db.scalars(_scoped(db, Movement).where(Movement.item_id == item_id).limit(1)).first())


def location_holds_stock(db: Session, location_id: str) -> bool:
    if any(s.on_hand > 0 for s in stock_levels(db, location_id=location_id)):
        return True
    q = _scoped(db, Unit).where(
        Unit.location_id == location_id, Unit.status.in_(("available", "reserved", "in_repair"))
    )
    return bool(db.scalars(q.limit(1)).first())


def lines_of(db: Session, loan_id: str) -> list[LoanLine]:
    return list(
        db.scalars(_scoped(db, LoanLine).where(LoanLine.loan_id == loan_id).order_by(LoanLine.position, LoanLine.id))
    )


def loans(db: Session) -> list[Loan]:
    return list(db.scalars(_scoped(db, Loan).order_by(Loan.due_at, Loan.id)))


def open_loans_of(db: Session, borrower_id: str) -> list[Loan]:
    q = _scoped(db, Loan).where(Loan.borrower_id == borrower_id, Loan.status.in_(OPEN_LOAN_STATUSES))
    return list(db.scalars(q))


def out_quantity(db: Session, item_id: str) -> float:
    q = (
        _scoped(db, LoanLine)
        .join(Loan, Loan.id == LoanLine.loan_id)
        .where(LoanLine.item_id == item_id, LoanLine.status == "out", Loan.status.in_(OUT_LOAN_STATUSES))
    )
    return sum(line.quantity for line in db.scalars(q))


def waiting_loans_for(db: Session, item_ids: set[str], exclude_loan_id: str) -> list[Loan]:
    """Requested or approved loans that want one of these items (blocks a borrower's extension, PRD rule 9)."""
    q = (
        _scoped(db, Loan)
        .join(LoanLine, LoanLine.loan_id == Loan.id)
        .where(Loan.status.in_(("requested", "approved")), LoanLine.item_id.in_(item_ids), Loan.id != exclude_loan_id)
    )
    return list(db.scalars(q).unique())


def all_loans_unscoped(db: Session, statuses: tuple[str, ...]) -> list[Loan]:
    """For the scheduler sweep; the caller runs it in platform scope across organisations."""
    return list(db.scalars(select(Loan).where(Loan.status.in_(statuses))))
