"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, case, func, select, text
from sqlalchemy.orm import Session

from ..domain.rules import OVERLAP_BLOCKING, SEAT_HOLDING
from .models import Assessment, LogEntry, Opening, OpeningSupervisor, Placement, Site, SiteSupervisor


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def for_update(db: Session, model, row_id: str):
    """Lock the row until the transaction ends, so two changes to it run one after the other (Postgres; SQLite
    serialises writers anyway). Used for seats of an opening and every status transition."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


# ---------------------------------------------------------------- pagination

# A cursor past this offset is not one this API handed out: the listing starts from the top instead.
MAX_OFFSET = 1_000_000


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


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


# ---------------------------------------------------------------- sites


def sites(db: Session, active: bool | None = None, q: str | None = None) -> list[Site]:
    query = _scoped(db, Site)
    if active is not None:
        query = query.where(Site.active.is_(active))
    if q:
        query = query.where(func.lower(Site.name).contains(q.lower(), autoescape=True))
    return list(db.scalars(query.order_by(Site.name, Site.id)))


def sites_by_id(db: Session, ids: list[str]) -> dict[str, Site]:
    if not ids:
        return {}
    return {s.id: s for s in db.scalars(_scoped(db, Site).where(Site.id.in_(ids)))}


def site_supervisors(db: Session, site_ids: list[str]) -> dict[str, list[str]]:
    """person_ids of each site's supervisors, in the order given."""
    out: dict[str, list[str]] = {sid: [] for sid in site_ids}
    if not site_ids:
        return out
    q = _scoped(db, SiteSupervisor).where(SiteSupervisor.site_id.in_(site_ids)).order_by(SiteSupervisor.position)
    for row in db.scalars(q):
        out[row.site_id].append(row.person_id)
    return out


def sites_supervised_by(db: Session, person_id: str) -> Select:
    """Ids of the sites where the person is a supervisor, as a subquery."""
    return (
        _scoped(db, SiteSupervisor)
        .where(SiteSupervisor.person_id == person_id)
        .with_only_columns(SiteSupervisor.site_id)
    )


def replace_site_supervisors(db: Session, site: Site, person_ids: list[str]) -> None:
    """The list is the site's own ordering, not a record of its own: it is replaced, not kept. The caller flushes
    the new rows (service._flush_unique), so a duplicate written at the same moment is a 409."""
    for row in db.scalars(_scoped(db, SiteSupervisor).where(SiteSupervisor.site_id == site.id)):
        db.delete(row)
    db.flush()
    for i, pid in enumerate(person_ids):
        db.add(SiteSupervisor(organisation_id=site.organisation_id, site_id=site.id, person_id=pid, position=i))


# ---------------------------------------------------------------- openings


def seats_filled_column(db: Session):
    """Seats filled of the opening in the outer query, as a correlated count."""
    return (
        _scoped(db, Placement)
        .where(Placement.opening_id == Opening.id, Placement.status.in_(SEAT_HOLDING))
        .with_only_columns(func.count(Placement.id))
        .scalar_subquery()
    )


def openings_query(
    db: Session,
    status: str | None = None,
    site_id: str | None = None,
    has_seats: bool | None = None,
    starts_after: date | None = None,
    site_ids: Select | None = None,
    applications_only: bool = False,
) -> Select:
    q = _scoped(db, Opening)
    if status:
        q = q.where(Opening.status == status)
    if site_id:
        q = q.where(Opening.site_id == site_id)
    if starts_after:
        q = q.where(Opening.starts_on > starts_after)
    if site_ids is not None:
        q = q.where(Opening.site_id.in_(site_ids))
    if applications_only:
        q = q.where(Opening.status == "open", Opening.allow_applications.is_(True))
    if has_seats is not None:
        filled = seats_filled_column(db)
        q = q.where(Opening.seats > filled if has_seats else Opening.seats <= filled)
    return q.order_by(Opening.starts_on, Opening.title, Opening.id)


def seats_filled(db: Session, opening_ids: list[str]) -> dict[str, int]:
    out = dict.fromkeys(opening_ids, 0)
    if not opening_ids:
        return out
    q = (
        _scoped(db, Placement)
        .where(Placement.opening_id.in_(opening_ids), Placement.status.in_(SEAT_HOLDING))
        .with_only_columns(Placement.opening_id, func.count(Placement.id))
        .group_by(Placement.opening_id)
    )
    for opening_id, count in db.execute(q):
        out[opening_id] = count
    return out


def opening_supervisors(db: Session, opening_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {oid: [] for oid in opening_ids}
    if not opening_ids:
        return out
    q = (
        _scoped(db, OpeningSupervisor)
        .where(OpeningSupervisor.opening_id.in_(opening_ids))
        .order_by(OpeningSupervisor.position)
    )
    for row in db.scalars(q):
        out[row.opening_id].append(row.person_id)
    return out


def replace_opening_supervisors(db: Session, opening: Opening, person_ids: list[str]) -> None:
    for row in db.scalars(_scoped(db, OpeningSupervisor).where(OpeningSupervisor.opening_id == opening.id)):
        db.delete(row)
    db.flush()
    for i, pid in enumerate(person_ids):
        db.add(
            OpeningSupervisor(organisation_id=opening.organisation_id, opening_id=opening.id, person_id=pid, position=i)
        )


def openings_by_id(db: Session, ids: list[str]) -> dict[str, Opening]:
    if not ids:
        return {}
    return {o.id: o for o in db.scalars(_scoped(db, Opening).where(Opening.id.in_(ids)))}


# ---------------------------------------------------------------- placements


def placements_query(
    db: Session,
    status: str | None = None,
    opening_id: str | None = None,
    site_id: str | None = None,
    trainee_id: str | None = None,
    supervisor_id: str | None = None,
) -> Select:
    q = _scoped(db, Placement)
    if status:
        q = q.where(Placement.status == status)
    if opening_id:
        q = q.where(Placement.opening_id == opening_id)
    if site_id:
        q = q.where(Placement.site_id == site_id)
    if trainee_id:
        q = q.where(Placement.trainee_id == trainee_id)
    if supervisor_id:
        q = q.where(Placement.supervisor_id == supervisor_id)
    return q.order_by(Placement.starts_on, Placement.created_at, Placement.id)


def placements_in(db: Session, opening_id: str, statuses: tuple[str, ...]) -> list[Placement]:
    q = _scoped(db, Placement).where(Placement.opening_id == opening_id, Placement.status.in_(statuses))
    return list(db.scalars(q.order_by(Placement.created_at, Placement.id)))


def trainee_placements(db: Session, trainee_id: str) -> list[Placement]:
    return list(db.scalars(_scoped(db, Placement).where(Placement.trainee_id == trainee_id)))


def lock_trainee(db: Session, trainee_id: str) -> None:
    """Serialise every overlap check of one trainee until the transaction ends, so two requests for different openings
    cannot both pass it (the row locks on the openings do not cover that). Postgres only: SQLite runs one writer at
    a time. The lock is the last one a request takes, after its opening or placement rows, so it cannot deadlock."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"field-training-trainee:{trainee_id}"},
        )


def overlapping(
    db: Session, trainee_id: str, start: date, end: date, exclude_id: str | None = None
) -> Placement | None:
    """The trainee's requested, assigned or active placement whose period overlaps start..end, if any."""
    q = _scoped(db, Placement).where(
        Placement.trainee_id == trainee_id,
        Placement.status.in_(OVERLAP_BLOCKING),
        Placement.starts_on <= end,
        Placement.ends_on >= start,
    )
    if exclude_id:
        q = q.where(Placement.id != exclude_id)
    return db.scalars(q).first()


def supervised_active(db: Session, supervisor_id: str) -> list[Placement]:
    q = _scoped(db, Placement).where(Placement.supervisor_id == supervisor_id, Placement.status == "active")
    return list(db.scalars(q))


def assigned_from(db: Session, today: date) -> list[Placement]:
    """Across organisations: the caller runs this in platform scope (the daily job). Locked, so a coordinator's
    early start at the same moment waits and then finds the placement already active."""
    q = select(Placement).where(Placement.status == "assigned", Placement.starts_on <= today)
    return list(db.scalars(q.order_by(Placement.starts_on, Placement.id).with_for_update()))


# ---------------------------------------------------------------- logbook


def logs(db: Session, placement_id: str, status: str | None = None) -> list[LogEntry]:
    q = _scoped(db, LogEntry).where(LogEntry.placement_id == placement_id)
    if status:
        q = q.where(LogEntry.status == status)
    return list(db.scalars(q.order_by(LogEntry.date.desc(), LogEntry.submitted_at.desc(), LogEntry.id)))


def minutes_by_status(db: Session, placement_ids: list[str]) -> dict[str, dict[str, int]]:
    """placement_id -> {log status -> minutes}."""
    out: dict[str, dict[str, int]] = {pid: {} for pid in placement_ids}
    if not placement_ids:
        return out
    q = (
        _scoped(db, LogEntry)
        .where(LogEntry.placement_id.in_(placement_ids))
        .with_only_columns(LogEntry.placement_id, LogEntry.status, func.sum(LogEntry.minutes))
        .group_by(LogEntry.placement_id, LogEntry.status)
    )
    for placement_id, status, minutes in db.execute(q):
        out[placement_id][status] = int(minutes or 0)
    return out


def awaiting_counts(db: Session, placement_ids: list[str]) -> dict[str, int]:
    """Submitted entries per placement: what the supervisor still has to verify or return."""
    out = dict.fromkeys(placement_ids, 0)
    if not placement_ids:
        return out
    q = (
        _scoped(db, LogEntry)
        .where(LogEntry.placement_id.in_(placement_ids), LogEntry.status == "submitted")
        .with_only_columns(LogEntry.placement_id, func.count(LogEntry.id))
        .group_by(LogEntry.placement_id)
    )
    for placement_id, count in db.execute(q):
        out[placement_id] = count
    return out


def trainee_minutes_on(db: Session, trainee_id: str, on: date, exclude_log_id: str | None = None) -> int:
    """Minutes the trainee has logged on one date across their placements, whatever the entries' status."""
    mine = _scoped(db, Placement).where(Placement.trainee_id == trainee_id).with_only_columns(Placement.id)
    q = (
        _scoped(db, LogEntry)
        .where(LogEntry.placement_id.in_(mine), LogEntry.date == on)
        .with_only_columns(func.coalesce(func.sum(LogEntry.minutes), 0))
    )
    if exclude_log_id:
        q = q.where(LogEntry.id != exclude_log_id)
    return int(db.scalar(q) or 0)


def log_dates(db: Session, placement_id: str) -> tuple[date | None, date | None]:
    q = (
        _scoped(db, LogEntry)
        .where(LogEntry.placement_id == placement_id)
        .with_only_columns(func.min(LogEntry.date), func.max(LogEntry.date))
    )
    first, last = db.execute(q).one()
    return first, last


def daily_minutes(db: Session, placement_id: str, start: date, end: date) -> dict[tuple[date, str], int]:
    """(date, status) -> minutes for the placement's entries between start and end."""
    q = (
        _scoped(db, LogEntry)
        .where(LogEntry.placement_id == placement_id, LogEntry.date >= start, LogEntry.date <= end)
        .with_only_columns(LogEntry.date, LogEntry.status, func.sum(LogEntry.minutes))
        .group_by(LogEntry.date, LogEntry.status)
    )
    return {(d, status): int(m or 0) for d, status, m in db.execute(q)}


# ---------------------------------------------------------------- assessments


def assessments(db: Session, placement_id: str) -> list[Assessment]:
    q = _scoped(db, Assessment).where(Assessment.placement_id == placement_id)
    mid_first = case((Assessment.stage == "mid", 0), else_=1)
    return list(db.scalars(q.order_by(mid_first, Assessment.recorded_at, Assessment.id)))


def final_outcomes(db: Session, placement_ids: list[str]) -> dict[str, str]:
    """placement_id -> outcome of its final assessment, for those that have one."""
    if not placement_ids:
        return {}
    q = _scoped(db, Assessment).where(Assessment.placement_id.in_(placement_ids), Assessment.stage == "final")
    return {a.placement_id: a.outcome for a in db.scalars(q)}
