"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..domain.rules import MILESTONE_OPEN
from .models import Guide, Member, Milestone, Project, Review, Submission


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def for_update(db: Session, model, row_id: str):
    """Lock the row so concurrent changes to it (a transition, a team change, a review) run one after the other."""
    return db.scalars(_scoped(db, model).where(model.id == row_id).with_for_update()).first()


# ---------------------------------------------------------------- pagination


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


# ---------------------------------------------------------------- projects


def _current_members(db: Session) -> Select:
    return _scoped(db, Member).where(Member.left_at.is_(None))


def _current_guides(db: Session) -> Select:
    return _scoped(db, Guide).where(Guide.removed_at.is_(None))


def projects_query(
    db: Session,
    status: str | None = None,
    kind: str | None = None,
    academic_year: str | None = None,
    guide_id: str | None = None,
    member_id: str | None = None,
    q: str | None = None,
) -> Select:
    query = _scoped(db, Project)
    if status:
        query = query.where(Project.status == status)
    if kind:
        query = query.where(Project.kind == kind)
    if academic_year:
        query = query.where(Project.academic_year == academic_year)
    if guide_id:
        guided = _current_guides(db).where(Guide.person_id == guide_id).with_only_columns(Guide.project_id)
        query = query.where(Project.id.in_(guided))
    if member_id:
        on_team = _current_members(db).where(Member.person_id == member_id).with_only_columns(Member.project_id)
        query = query.where(Project.id.in_(on_team))
    if q:
        query = query.where(func.lower(Project.title).contains(q.lower(), autoescape=True))
    return query.order_by(Project.ends_on, Project.title, Project.id)


def projects_by_id(db: Session, ids: list[str]) -> dict[str, Project]:
    if not ids:
        return {}
    return {p.id: p for p in db.scalars(_scoped(db, Project).where(Project.id.in_(ids)))}


def members_of(db: Session, project_ids: list[str], current_only: bool = True) -> dict[str, list[Member]]:
    """Team of each project in joining order: the current team, or every member who ever joined."""
    out: dict[str, list[Member]] = {pid: [] for pid in project_ids}
    if not project_ids:
        return out
    query = (_current_members(db) if current_only else _scoped(db, Member)).where(Member.project_id.in_(project_ids))
    for m in db.scalars(query.order_by(Member.joined_at, Member.id)):
        out[m.project_id].append(m)
    return out


def guides_of(db: Session, project_ids: list[str]) -> dict[str, list[Guide]]:
    """Current guides of each project, in assignment order."""
    out: dict[str, list[Guide]] = {pid: [] for pid in project_ids}
    if not project_ids:
        return out
    query = _current_guides(db).where(Guide.project_id.in_(project_ids)).order_by(Guide.assigned_at, Guide.id)
    for g in db.scalars(query):
        out[g.project_id].append(g)
    return out


def membership(db: Session, project_id: str, person_id: str) -> Member | None:
    query = _current_members(db).where(Member.project_id == project_id, Member.person_id == person_id)
    return db.scalars(query).first()


def guiding(db: Session, project_id: str, person_id: str) -> Guide | None:
    query = _current_guides(db).where(Guide.project_id == project_id, Guide.person_id == person_id)
    return db.scalars(query).first()


def member_project_ids(db: Session, person_id: str) -> list[str]:
    return list(
        db.scalars(_current_members(db).where(Member.person_id == person_id).with_only_columns(Member.project_id))
    )


def guided_project_ids(db: Session, person_id: str) -> list[str]:
    return list(db.scalars(_current_guides(db).where(Guide.person_id == person_id).with_only_columns(Guide.project_id)))


# ---------------------------------------------------------------- milestones, submissions and reviews


def milestones_of(db: Session, project_ids: list[str]) -> dict[str, list[Milestone]]:
    """Milestones of each project in due order."""
    out: dict[str, list[Milestone]] = {pid: [] for pid in project_ids}
    if not project_ids:
        return out
    query = _scoped(db, Milestone).where(Milestone.project_id.in_(project_ids))
    for m in db.scalars(query.order_by(Milestone.due_on, Milestone.created_at, Milestone.id)):
        out[m.project_id].append(m)
    return out


def open_milestones_due(db: Session, project_ids: list[str], until: date) -> list[Milestone]:
    """Pending or returned milestones of these projects due on or before `until` (overdue ones too), earliest first."""
    if not project_ids:
        return []
    query = _scoped(db, Milestone).where(
        Milestone.project_id.in_(project_ids), Milestone.status.in_(MILESTONE_OPEN), Milestone.due_on <= until
    )
    return list(db.scalars(query.order_by(Milestone.due_on, Milestone.created_at, Milestone.id)))


def submitted_milestones(db: Session, project_ids: list[str]) -> list[Milestone]:
    if not project_ids:
        return []
    query = _scoped(db, Milestone).where(Milestone.project_id.in_(project_ids), Milestone.status == "submitted")
    return list(db.scalars(query))


def submissions(db: Session, project_id: str, milestone_id: str | None) -> list[Submission]:
    """Every version for a milestone, or every final submission of the project (milestone_id None), oldest first."""
    query = _scoped(db, Submission).where(Submission.project_id == project_id)
    if milestone_id is None:
        query = query.where(Submission.milestone_id.is_(None))
    else:
        query = query.where(Submission.milestone_id == milestone_id)
    return list(db.scalars(query.order_by(Submission.version)))


def latest_submission(db: Session, project_id: str, milestone_id: str | None) -> Submission | None:
    rows = submissions(db, project_id, milestone_id)
    return rows[-1] if rows else None


def latest_submission_at(db: Session, milestone_ids: list[str]) -> dict[str, object]:
    if not milestone_ids:
        return {}
    query = (
        _scoped(db, Submission)
        .where(Submission.milestone_id.in_(milestone_ids))
        .with_only_columns(Submission.milestone_id, func.max(Submission.submitted_at))
        .group_by(Submission.milestone_id)
    )
    return dict(db.execute(query).all())


def reviews_of(db: Session, submission_ids: list[str]) -> dict[str, Review]:
    if not submission_ids:
        return {}
    return {r.submission_id: r for r in db.scalars(_scoped(db, Review).where(Review.submission_id.in_(submission_ids)))}


def overdue_candidates(db: Session, before: date) -> list[Milestone]:
    """Across organisations: pending or returned milestones due before `before` not yet flagged overdue, of active
    projects. The caller runs this in platform scope (the daily job)."""
    active = select(Project.id).where(Project.status == "active")
    query = select(Milestone).where(
        Milestone.status.in_(MILESTONE_OPEN),
        Milestone.due_on < before,
        Milestone.overdue_flagged_at.is_(None),
        Milestone.project_id.in_(active),
    )
    return list(db.scalars(query.order_by(Milestone.due_on, Milestone.id)))
