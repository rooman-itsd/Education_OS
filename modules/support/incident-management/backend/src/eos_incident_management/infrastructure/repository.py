"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64
import binascii
from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import CorrectiveAction, Incident, NumberSequence, Problem, Rca, Reference, TimelineUpdate

# The largest offset a cursor may carry. Far beyond any real list, and small enough that OFFSET never overflows.
MAX_OFFSET = 10**6


class InvalidCursorError(ValueError):
    """The cursor was not one this module handed out (422)."""


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def locked(db: Session, model, row_id: str):
    """The row, locked until the transaction ends (FOR UPDATE on Postgres; SQLite locks the whole database on write).
    Used before a check-then-insert under the row, such as the one RCA of a problem or the one record of a reference
    per incident, so two requests at the same moment run one after the other."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


def _like(text: str) -> str:
    """A LIKE pattern that matches `text` literally, case-insensitively (with escape="\\")."""
    escaped = text.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------------------------------------------------------------- pagination (opaque cursor = offset)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """0 without a cursor. A cursor this module did not hand out, or one past MAX_OFFSET, is refused."""
    if not cursor:
        return 0
    if len(cursor) > 16:  # str(MAX_OFFSET) encodes to 12 characters
        raise InvalidCursorError(cursor)
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
    except (ValueError, UnicodeError, binascii.Error):
        raise InvalidCursorError(cursor) from None
    if not raw.isdigit() or int(raw) > MAX_OFFSET:
        raise InvalidCursorError(cursor)
    return int(raw)


def page_of(rows: list, offset: int, limit: int) -> tuple[list, str | None]:
    """A page of rows already filtered in Python (service labels and overdue are matched when read)."""
    chunk = rows[offset : offset + limit]
    more = offset + limit < len(rows) and offset + limit <= MAX_OFFSET
    return chunk, encode_cursor(offset + limit) if more else None


# ---------------------------------------------------------------- numbers


def next_number(db: Session, organisation_id: str, kind: str) -> int:
    """The next number of the organisation's sequence for `kind`. The row is locked (FOR UPDATE on Postgres) so two
    incidents or problems reported at the same time never get the same number; the unique (organisation_id, number)
    indexes back this. FOR UPDATE locks nothing while the row does not exist, so it is first created with ON CONFLICT
    DO NOTHING: of two first numbers at the same time, the second insert waits for the first and then does nothing."""
    insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(NumberSequence)
        .values(organisation_id=organisation_id, kind=kind, last_number=0)
        .on_conflict_do_nothing(index_elements=["organisation_id", "kind"])
    )
    q = (
        select(NumberSequence)
        .where(NumberSequence.organisation_id == organisation_id, NumberSequence.kind == kind)
        .with_for_update()
    )
    row = db.scalars(q).one()
    row.last_number += 1
    db.flush()
    return row.last_number


# ---------------------------------------------------------------- incidents


def incidents(
    db: Session,
    *,
    statuses: list[str] | None = None,
    severity: str | None = None,
    lead_id: str | None = None,
    problem_id: str | None = None,
    q: str | None = None,
) -> list[Incident]:
    """Matching incidents, newest first (GET /incidents). The service label filter runs in Python."""
    query = _scoped(db, Incident)
    if statuses:
        query = query.where(Incident.status.in_(statuses))
    if severity:
        query = query.where(Incident.severity == severity)
    if lead_id:
        query = query.where(Incident.lead_id == lead_id)
    if problem_id:
        query = query.where(Incident.problem_id == problem_id)
    if q:
        like = _like(q)
        query = query.where(
            or_(
                func.lower(Incident.number).like(like, escape="\\"),
                func.lower(Incident.title).like(like, escape="\\"),
            )
        )
    return list(db.scalars(query.order_by(Incident.created_at.desc(), Incident.number.desc())))


def incident_states(db: Session) -> list[tuple[str, str]]:
    """(status, severity) of every incident of the organisation (GET /stats/open)."""
    query = scoped(db, select(Incident.status, Incident.severity), Incident)
    return [(status, severity) for status, severity in db.execute(query)]


def incidents_of_problem(db: Session, problem_id: str) -> list[Incident]:
    query = _scoped(db, Incident).where(Incident.problem_id == problem_id)
    return list(db.scalars(query.order_by(Incident.created_at, Incident.number)))


def incident_counts(db: Session, problem_ids: list[str]) -> dict[str, int]:
    if not problem_ids:
        return {}
    query = scoped(
        db, select(Incident.problem_id, func.count()).where(Incident.problem_id.in_(problem_ids)), Incident
    ).group_by(Incident.problem_id)
    return {problem_id: count for problem_id, count in db.execute(query)}


def timeline(db: Session, incident_id: str) -> list[TimelineUpdate]:
    """Oldest first."""
    query = _scoped(db, TimelineUpdate).where(TimelineUpdate.incident_id == incident_id)
    return list(db.scalars(query.order_by(TimelineUpdate.created_at, TimelineUpdate.id)))


def references(db: Session, incident_id: str) -> list[Reference]:
    query = _scoped(db, Reference).where(Reference.incident_id == incident_id)
    return list(db.scalars(query.order_by(Reference.created_at, Reference.id)))


def reference_to(db: Session, incident_id: str, module: str, entity: str, ref_id: str) -> Reference | None:
    query = _scoped(db, Reference).where(
        Reference.incident_id == incident_id,
        Reference.ref_module == module,
        Reference.ref_entity == entity,
        Reference.ref_id == ref_id,
    )
    return db.scalars(query).first()


# ---------------------------------------------------------------- problems, RCAs and actions


def problems(
    db: Session, *, statuses: list[str] | None = None, owner_id: str | None = None, q: str | None = None
) -> list[Problem]:
    """Matching problems, newest first (GET /problems). The service label filter runs in Python."""
    query = _scoped(db, Problem)
    if statuses:
        query = query.where(Problem.status.in_(statuses))
    if owner_id:
        query = query.where(Problem.owner_id == owner_id)
    if q:
        like = _like(q)
        query = query.where(
            or_(
                func.lower(Problem.number).like(like, escape="\\"),
                func.lower(Problem.title).like(like, escape="\\"),
            )
        )
    return list(db.scalars(query.order_by(Problem.created_at.desc(), Problem.number.desc())))


def problems_by_id(db: Session, ids: set[str]) -> dict[str, Problem]:
    if not ids:
        return {}
    return {p.id: p for p in db.scalars(_scoped(db, Problem).where(Problem.id.in_(ids)))}


def rca(db: Session, problem_id: str) -> Rca | None:
    return db.scalars(_scoped(db, Rca).where(Rca.problem_id == problem_id)).first()


def actions(
    db: Session,
    *,
    problem_id: str | None = None,
    owner_id: str | None = None,
    status: str | None = None,
    due_before: date | None = None,
) -> list[CorrectiveAction]:
    """Matching corrective actions, soonest due first (GET /actions, and the actions of a problem)."""
    query = _scoped(db, CorrectiveAction)
    if problem_id:
        query = query.where(CorrectiveAction.problem_id == problem_id)
    if owner_id:
        query = query.where(CorrectiveAction.owner_id == owner_id)
    if status:
        query = query.where(CorrectiveAction.status == status)
    if due_before:
        query = query.where(CorrectiveAction.due_date < due_before)
    order = (CorrectiveAction.due_date, CorrectiveAction.created_at, CorrectiveAction.id)
    return list(db.scalars(query.order_by(*order)))
