"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal

from eos_core.db import scoped
from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import Session

from ..domain.rules import RESERVATION_ACTIVE
from .models import Copy, DigitalResource, Fine, Loan, LoanPolicy, Member, Reservation, Title


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


# ---------------------------------------------------------------- pagination

MAX_LIMIT = 100


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


# A cursor past this is not one we handed out; like any other bad cursor it starts from the top.
MAX_OFFSET = 1_000_000


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, UnicodeDecodeError):
        return 0
    return offset if 0 <= offset <= MAX_OFFSET else 0


def page(db: Session, query: Select, cursor: str | None, limit: int) -> tuple[list, str | None]:
    offset = decode_cursor(cursor)
    rows = list(db.scalars(query.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    return rows[:limit], encode_cursor(offset + limit) if more else None


# ---------------------------------------------------------------- catalogue


def titles_query(db: Session, q: str | None = None, kind: str | None = None) -> Select:
    query = _scoped(db, Title)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Title.title).like(like),
                func.lower(func.coalesce(Title.isbn, "")).like(like),
                func.lower(cast(Title.authors, String)).like(like),
                func.lower(cast(Title.subjects, String)).like(like),
            )
        )
    if kind:
        query = query.where(Title.kind == kind)
    return query.order_by(Title.title, Title.id)


def title_by_isbn(db: Session, isbn: str) -> Title | None:
    return db.scalars(_scoped(db, Title).where(Title.isbn == isbn)).first()


def copies_of(db: Session, title_ids: list[str]) -> list[Copy]:
    if not title_ids:
        return []
    return list(db.scalars(_scoped(db, Copy).where(Copy.title_id.in_(title_ids)).order_by(Copy.accession_no)))


def copy_by(db: Session, *, accession_no: str | None = None, barcode: str | None = None) -> Copy | None:
    q = _scoped(db, Copy)
    q = q.where(Copy.accession_no == accession_no) if accession_no is not None else q.where(Copy.barcode == barcode)
    return db.scalars(q).first()


def copy_for_update(db: Session, *, copy_id: str | None = None, barcode: str | None = None) -> Copy | None:
    """Lock the copy so two desks never issue or return it at once (one active loan, one active hold)."""
    q = _scoped(db, Copy)
    q = q.where(Copy.id == copy_id) if copy_id is not None else q.where(Copy.barcode == barcode)
    return db.scalars(q.with_for_update()).first()


def first_available_copy(db: Session, title_id: str) -> Copy | None:
    q = _scoped(db, Copy).where(Copy.title_id == title_id, Copy.status == "available")
    return db.scalars(q.order_by(Copy.accession_no)).first()


# ---------------------------------------------------------------- policies and members


def policies(db: Session) -> list[LoanPolicy]:
    return list(db.scalars(_scoped(db, LoanPolicy).order_by(LoanPolicy.member_category)))


def policy_for(db: Session, category: str, organisation_id: str | None = None) -> LoanPolicy | None:
    """organisation_id pins the lookup when a daily job runs in platform scope, where every category name repeats."""
    q = _scoped(db, LoanPolicy).where(LoanPolicy.member_category == category)
    if organisation_id:
        q = q.where(LoanPolicy.organisation_id == organisation_id)
    return db.scalars(q).first()


def member(db: Session, person_id: str, organisation_id: str | None = None, *, lock: bool = False) -> Member | None:
    """lock: two issues to one member run one after the other, so both cannot pass max_loans."""
    q = _scoped(db, Member).where(Member.person_id == person_id)
    if organisation_id:
        q = q.where(Member.organisation_id == organisation_id)
    if lock:
        q = q.with_for_update()
    return db.scalars(q).first()


def members_query(db: Session, q: str | None = None, blocked: bool | None = None) -> Select:
    query = _scoped(db, Member)
    if q:
        query = query.where(func.lower(func.coalesce(Member.person_name, "")).like(f"%{q.lower()}%"))
    if blocked is not None:
        query = query.where(Member.blocked.is_(blocked))
    return query.order_by(Member.person_name, Member.person_id)


# ---------------------------------------------------------------- loans


def active_loan_for_copy(db: Session, copy_id: str) -> Loan | None:
    return db.scalars(_scoped(db, Loan).where(Loan.copy_id == copy_id, Loan.status == "active")).first()


def active_loans_of(db: Session, person_id: str) -> list[Loan]:
    q = _scoped(db, Loan).where(Loan.person_id == person_id, Loan.status == "active")
    return list(db.scalars(q.order_by(Loan.due_on, Loan.id)))


def loans_query(
    db: Session, today: date, status: str | None = None, overdue: bool | None = None, person_id: str | None = None
) -> Select:
    q = _scoped(db, Loan)
    if status:
        q = q.where(Loan.status == status)
    if person_id:
        q = q.where(Loan.person_id == person_id)
    if overdue is True:
        q = q.where(Loan.status == "active", Loan.due_on < today)
    elif overdue is False:
        q = q.where(or_(Loan.status != "active", Loan.due_on >= today))
    return q.order_by(Loan.due_on, Loan.id)


def unflagged_overdue_loans(db: Session, today: date) -> list[Loan]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    q = select(Loan).where(Loan.status == "active", Loan.due_on < today, Loan.overdue_flagged_at.is_(None))
    return list(db.scalars(q))


# ---------------------------------------------------------------- reservations


def waiting_queue(db: Session, title_id: str) -> list[Reservation]:
    q = _scoped(db, Reservation).where(Reservation.title_id == title_id, Reservation.status == "waiting")
    return list(db.scalars(q.order_by(Reservation.placed_at, Reservation.id)))


def active_reservation(db: Session, person_id: str, title_id: str) -> Reservation | None:
    q = _scoped(db, Reservation).where(
        Reservation.person_id == person_id,
        Reservation.title_id == title_id,
        Reservation.status.in_(RESERVATION_ACTIVE),
    )
    return db.scalars(q).first()


def ready_reservation_for_copy(db: Session, copy_id: str) -> Reservation | None:
    q = _scoped(db, Reservation).where(Reservation.held_copy_id == copy_id, Reservation.status == "ready")
    return db.scalars(q).first()


def reservations_query(db: Session, status: str | None = None, title_id: str | None = None) -> Select:
    q = _scoped(db, Reservation)
    if status:
        q = q.where(Reservation.status == status)
    if title_id:
        q = q.where(Reservation.title_id == title_id)
    return q.order_by(Reservation.placed_at, Reservation.id)


def my_reservations(db: Session, person_id: str) -> list[Reservation]:
    q = _scoped(db, Reservation).where(Reservation.person_id == person_id, Reservation.status.in_(RESERVATION_ACTIVE))
    return list(db.scalars(q.order_by(Reservation.placed_at, Reservation.id)))


def expired_holds(db: Session, today: date) -> list[Reservation]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    q = select(Reservation).where(Reservation.status == "ready", Reservation.hold_expires_on < today)
    return list(db.scalars(q.order_by(Reservation.hold_expires_on, Reservation.id)))


# ---------------------------------------------------------------- fines


def fines_query(db: Session, status: str | None = None, person_id: str | None = None) -> Select:
    q = _scoped(db, Fine)
    if status:
        q = q.where(Fine.status == status)
    if person_id:
        q = q.where(Fine.person_id == person_id)
    return q.order_by(Fine.raised_at.desc(), Fine.id)


def open_fines_of(db: Session, person_id: str) -> list[Fine]:
    q = _scoped(db, Fine).where(Fine.person_id == person_id, Fine.status == "open")
    return list(db.scalars(q.order_by(Fine.raised_at, Fine.id)))


def open_fines_total(db: Session, person_id: str) -> Decimal:
    return sum((f.amount for f in open_fines_of(db, person_id)), Decimal("0.00"))


# ---------------------------------------------------------------- digital resources


def digital_resources(
    db: Session, q: str | None = None, kind: str | None = None, active_only: bool = False
) -> list[DigitalResource]:
    query = _scoped(db, DigitalResource)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(DigitalResource.title).like(like),
                func.lower(func.coalesce(DigitalResource.provider, "")).like(like),
            )
        )
    if kind:
        query = query.where(DigitalResource.kind == kind)
    if active_only:
        query = query.where(DigitalResource.active.is_(True))
    return list(db.scalars(query.order_by(DigitalResource.title, DigitalResource.id)))
