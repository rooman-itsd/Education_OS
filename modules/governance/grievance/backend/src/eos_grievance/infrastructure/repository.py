"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces the
same rule underneath."""

from __future__ import annotations

import base64
import binascii

from eos_core.db import scoped
from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session

from ..domain.cases import OPEN_STATUSES
from .models import Appeal, Committee, CommitteeMember, Decision, Grievance, Proceeding, Update

# An opaque cursor is an offset. Larger offsets, and anything that does not decode, are refused (422) rather than handed
# to the database.
MAX_OFFSET = 10**6
MAX_CURSOR_LEN = 16


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str, *, lock: bool = False):
    """One row of the caller's organisation, or None. lock: FOR UPDATE on Postgres, so two requests changing the same
    row run one after the other and the second sees the first's result."""
    query = _scoped(db, model).where(model.id == row_id)
    if lock:
        query = query.with_for_update()
    return db.scalars(query).first()


# ---------------------------------------------------------------- pagination (opaque cursor = offset)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """The offset in a cursor from encode_cursor; ValueError for anything else or an offset above MAX_OFFSET."""
    if not cursor:
        return 0
    if len(cursor) > MAX_CURSOR_LEN:
        raise ValueError("cursor too long")
    try:
        text_ = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    except (binascii.Error, UnicodeError) as e:
        raise ValueError("cursor does not decode") from e
    if not (text_.isascii() and text_.isdigit()):
        raise ValueError("cursor is not an offset")
    offset = int(text_)
    if offset > MAX_OFFSET:
        raise ValueError("cursor offset too large")
    return offset


def slice_page(rows: list, offset: int, limit: int) -> tuple[list, str | None]:
    """One page of an already ordered list, and the cursor of the next."""
    window = rows[offset : offset + limit]
    return window, encode_cursor(offset + limit) if len(rows) > offset + limit else None


# ---------------------------------------------------------------- committees


def committees(db: Session, kind: str | None = None, active: bool | None = None) -> list[Committee]:
    q = _scoped(db, Committee)
    if kind:
        q = q.where(Committee.kind == kind)
    if active is not None:
        q = q.where(Committee.active.is_(active))
    return list(db.scalars(q.order_by(Committee.name, Committee.id)))


def committee_by_name(db: Session, name: str) -> Committee | None:
    return db.scalars(_scoped(db, Committee).where(func.lower(Committee.name) == name.lower())).first()


def active_committees_of_kind(db: Session, kind: str) -> list[Committee]:
    q = _scoped(db, Committee).where(Committee.kind == kind, Committee.active.is_(True))
    return list(db.scalars(q.order_by(Committee.created_at, Committee.id)))


def members_of(db: Session, committee_ids: list[str]) -> dict[str, list[CommitteeMember]]:
    out: dict[str, list[CommitteeMember]] = {cid: [] for cid in committee_ids}
    if not committee_ids:
        return out
    q = _scoped(db, CommitteeMember).where(CommitteeMember.committee_id.in_(committee_ids))
    for m in db.scalars(q.order_by(CommitteeMember.person_id)):
        out[m.committee_id].append(m)
    return out


def memberships_of(db: Session, person_id: str) -> dict[str, str]:
    """committee id -> the person's role there, for every committee they sit on."""
    q = _scoped(db, CommitteeMember).where(CommitteeMember.person_id == person_id)
    return {m.committee_id: m.role for m in db.scalars(q)}


def replace_members(db: Session, committee_id: str, members: list[dict], organisation_id: str) -> None:
    for row in members_of(db, [committee_id])[committee_id]:
        db.delete(row)
    db.flush()
    for m in members:
        db.add(
            CommitteeMember(
                organisation_id=organisation_id, committee_id=committee_id, person_id=m["person_id"], role=m["role"]
            )
        )


def committee_has_open_cases(db: Session, committee_id: str) -> bool:
    """Open cases the committee handles: its own, and appeals sent to it that are not yet closed."""
    own = _scoped(db, Grievance).where(
        Grievance.committee_id == committee_id,
        Grievance.status.in_([s for s in OPEN_STATUSES if s not in ("appealed", "appeal_decided")]),
    )
    if db.scalars(own.limit(1)).first() is not None:
        return True
    appealed = (
        _scoped(db, Grievance)
        .join(Appeal, Appeal.grievance_id == Grievance.id)
        .where(Appeal.committee_id == committee_id, Grievance.status.in_(("appealed", "appeal_decided")))
    )
    return db.scalars(appealed.limit(1)).first() is not None


# ---------------------------------------------------------------- cases


def next_sequence(db: Session) -> int:
    """The next per-organisation case number. On Postgres the organisation's filings are serialised, so two at once do
    not take the same number; SQLite runs one writer at a time. The unique constraint is the last guard."""
    org = db.info.get("organisation_id")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"grievance-number:{org}"})
    top = db.scalar(scoped(db, select(func.max(Grievance.sequence)), Grievance))
    return (top or 0) + 1


def appeals_for(db: Session, case_ids: list[str]) -> dict[str, Appeal]:
    if not case_ids:
        return {}
    return {a.grievance_id: a for a in db.scalars(_scoped(db, Appeal).where(Appeal.grievance_id.in_(case_ids)))}


def decision_of(db: Session, case_id: str) -> Decision | None:
    return db.scalars(_scoped(db, Decision).where(Decision.grievance_id == case_id)).first()


def updates_of(db: Session, case_id: str) -> list[Update]:
    q = _scoped(db, Update).where(Update.grievance_id == case_id)
    return list(db.scalars(q.order_by(Update.created_at, Update.id)))


def proceedings_of(db: Session, case_id: str) -> list[Proceeding]:
    q = _scoped(db, Proceeding).where(Proceeding.grievance_id == case_id)
    return list(db.scalars(q.order_by(Proceeding.held_on, Proceeding.created_at, Proceeding.id)))


def my_cases(db: Session, person_id: str, statuses: list[str] | None) -> Select:
    q = _scoped(db, Grievance).where(Grievance.complainant_id == person_id)
    if statuses:
        q = q.where(Grievance.status.in_(statuses))
    return q.order_by(Grievance.filed_at.desc(), Grievance.id.desc())


def committee_cases(
    db: Session,
    committee_ids: list[str],
    *,
    committee_id: str | None = None,
    track: str | None = None,
    statuses: list[str] | None = None,
) -> Select:
    """Cases of the committees given: those filed with them, and those appealed to them."""
    appealed_here = select(Appeal.grievance_id).where(Appeal.committee_id.in_(committee_ids))
    q = _scoped(db, Grievance).where(or_(Grievance.committee_id.in_(committee_ids), Grievance.id.in_(appealed_here)))
    if committee_id:
        appealed_to = select(Appeal.grievance_id).where(Appeal.committee_id == committee_id)
        q = q.where(or_(Grievance.committee_id == committee_id, Grievance.id.in_(appealed_to)))
    if track:
        q = q.where(Grievance.track == track)
    if statuses:
        q = q.where(Grievance.status.in_(statuses))
    return q.order_by(Grievance.filed_at.desc(), Grievance.id.desc())


def open_cases(db: Session) -> list[tuple[str, str, str, object, str | None]]:
    """(id, track, status, filed_at, handling committee id) of every open case, for the counts. Appealed cases are
    counted under the ombudsperson committee they were sent to."""
    q = (
        scoped(
            db,
            select(
                Grievance.id,
                Grievance.track,
                Grievance.status,
                Grievance.filed_at,
                func.coalesce(Appeal.committee_id, Grievance.committee_id),
                Grievance.committee_id,
            ).outerjoin(Appeal, Appeal.grievance_id == Grievance.id),
            Grievance,
        )
        .where(Grievance.status.in_(OPEN_STATUSES))
        .order_by(Grievance.filed_at, Grievance.id)
    )
    rows = []
    for case_id, track, status, filed_at, appeal_or_own, own in db.execute(q):
        handling = appeal_or_own if status in ("appealed", "appeal_decided") else own
        rows.append((case_id, track, status, filed_at, handling))
    return rows
