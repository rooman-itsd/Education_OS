"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date, datetime, time, timedelta

from eos_core.db import scoped
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from ..domain.tickets import OPEN_STATUSES, PRIORITIES_URGENT_FIRST, RESOLVED
from .models import Category, Comment, Queue, Ticket, TicketLink, TicketNumberSequence

UTC_MIDNIGHT = time(0, 0)


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


def page(db: Session, query: Select, cursor: str | None, limit: int) -> tuple[list, str | None]:
    offset = decode_cursor(cursor)
    rows = list(db.scalars(query.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    return rows[:limit], encode_cursor(offset + limit) if more else None


# ---------------------------------------------------------------- queues and categories


def queues(db: Session, active: bool | None = None) -> list[Queue]:
    q = _scoped(db, Queue)
    if active is not None:
        q = q.where(Queue.active.is_(active))
    return list(db.scalars(q.order_by(Queue.name, Queue.id)))


def queue_by_name(db: Session, name: str) -> Queue | None:
    return db.scalars(_scoped(db, Queue).where(Queue.name == name)).first()


def member_queue_ids(db: Session, person_id: str) -> set[str]:
    """The queues whose member_ids hold this person. member_ids is a JSON list, so it is read and filtered here;
    an organisation has few queues."""
    return {q.id for q in queues(db) if person_id in (q.member_ids or [])}


def open_counts_by_queue(db: Session) -> dict[str, int]:
    q = (
        scoped(db, select(Ticket.queue_id, func.count()), Ticket)
        .where(Ticket.status.in_(OPEN_STATUSES))
        .group_by(Ticket.queue_id)
    )
    return {queue_id: count for queue_id, count in db.execute(q)}


def categories(db: Session, active: bool | None = None) -> list[Category]:
    q = _scoped(db, Category)
    if active is not None:
        q = q.where(Category.active.is_(active))
    return list(db.scalars(q.order_by(Category.parent_id.is_not(None), Category.name, Category.id)))


def category_by_name(db: Session, parent_id: str | None, name: str) -> Category | None:
    parent = Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
    return db.scalars(_scoped(db, Category).where(parent, Category.name == name)).first()


def has_children(db: Session, category_id: str) -> bool:
    return db.scalars(_scoped(db, Category).where(Category.parent_id == category_id)).first() is not None


# ---------------------------------------------------------------- tickets


def next_ticket_number(db: Session, organisation_id: str) -> int:
    """The next number of the organisation's sequence. The row is locked (FOR UPDATE on Postgres) so two tickets
    raised at the same time never get the same number; the unique (organisation_id, number) index backs this."""
    q = select(TicketNumberSequence).where(TicketNumberSequence.organisation_id == organisation_id).with_for_update()
    row = db.scalars(q).first()
    if row is None:
        row = TicketNumberSequence(organisation_id=organisation_id, last_number=0)
        db.add(row)
    row.last_number += 1
    db.flush()
    return row.last_number


def tickets_query(
    db: Session,
    *,
    queue_ids: set[str] | None,
    statuses: list[str] | None = None,
    priority: str | None = None,
    queue_id: str | None = None,
    category_id: str | None = None,
    assignee: str | None = None,
    me: str | None = None,
    requester_id: str | None = None,
    q: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort: str = "newest",
) -> Select:
    """GET /tickets. queue_ids None means every queue (helpdesk:ticket:read-all)."""
    query = _scoped(db, Ticket)
    if queue_ids is not None:
        query = query.where(Ticket.queue_id.in_(queue_ids or {""}))
    if statuses:
        query = query.where(Ticket.status.in_(statuses))
    if priority:
        query = query.where(Ticket.priority == priority)
    if queue_id:
        query = query.where(Ticket.queue_id == queue_id)
    if category_id:
        query = query.where(Ticket.category_id == category_id)
    if assignee == "unassigned":
        query = query.where(Ticket.assignee_id.is_(None))
    elif assignee == "me":
        query = query.where(Ticket.assignee_id == me)
    elif assignee:
        query = query.where(Ticket.assignee_id == assignee)
    if requester_id:
        query = query.where(Ticket.requester_id == requester_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Ticket.number.ilike(like), Ticket.title.ilike(like)))
    if created_from:
        query = query.where(Ticket.created_at >= datetime.combine(created_from, UTC_MIDNIGHT))
    if created_to:
        query = query.where(Ticket.created_at < datetime.combine(created_to + timedelta(days=1), UTC_MIDNIGHT))
    return query.order_by(*_order(sort))


def _order(sort: str) -> list:
    if sort == "oldest":
        return [Ticket.created_at.asc(), Ticket.id]
    if sort == "priority":
        rank = case({p: i for i, p in enumerate(PRIORITIES_URGENT_FIRST)}, value=Ticket.priority, else_=99)
        return [rank, Ticket.created_at.desc(), Ticket.id]
    return [Ticket.created_at.desc(), Ticket.id]


def my_tickets_query(db: Session, requester_id: str, statuses: list[str] | None = None) -> Select:
    query = _scoped(db, Ticket).where(Ticket.requester_id == requester_id)
    if statuses:
        query = query.where(Ticket.status.in_(statuses))
    return query.order_by(Ticket.created_at.desc(), Ticket.id)


def open_tickets(db: Session, queue_ids: frozenset[str] | None, assignee_id: str | None) -> list[Ticket]:
    """Open tickets for the open-by-priority counts, read through the (organisation_id, status, priority,
    queue_id) index."""
    query = _scoped(db, Ticket).where(Ticket.status.in_(OPEN_STATUSES))
    if queue_ids is not None:
        query = query.where(Ticket.queue_id.in_(queue_ids or {""}))
    if assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)
    return list(db.scalars(query))


def comments(db: Session, ticket_id: str, public_only: bool) -> list[Comment]:
    query = _scoped(db, Comment).where(Comment.ticket_id == ticket_id)
    if public_only:
        query = query.where(Comment.visibility == "public")
    return list(db.scalars(query.order_by(Comment.created_at, Comment.id)))


def links(db: Session, ticket_id: str) -> list[TicketLink]:
    query = _scoped(db, TicketLink).where(TicketLink.ticket_id == ticket_id)
    return list(db.scalars(query.order_by(TicketLink.created_at, TicketLink.id)))


def same_link(db: Session, ticket_id: str, module: str, entity: str, ref_id: str) -> TicketLink | None:
    query = _scoped(db, TicketLink).where(
        TicketLink.ticket_id == ticket_id,
        TicketLink.module == module,
        TicketLink.entity == entity,
        TicketLink.ref_id == ref_id,
    )
    return db.scalars(query).first()


def resolved_tickets(db: Session) -> list[Ticket]:
    """Across organisations: the caller runs this in platform scope (the daily auto-close job)."""
    return list(db.scalars(select(Ticket).where(Ticket.status == RESOLVED)))
