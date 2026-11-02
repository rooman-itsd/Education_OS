"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from eos_core.db import scoped
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from .models import AnnotationAthlete, AthleteLink, Drill, DrillTag, SessionAttendee


def query(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str | None):
    if not row_id:
        return None
    return db.scalars(query(db, model).where(model.id == row_id)).first()


def first_by(db: Session, model, **values):
    q = query(db, model)
    for name, value in values.items():
        q = q.where(getattr(model, name) == value)
    return db.scalars(q).first()


def ids_present(db: Session, model, ids: Iterable[str]) -> set[str]:
    ids = set(ids)
    if not ids:
        return set()
    return set(db.scalars(query(db, model).with_only_columns(model.id).where(model.id.in_(ids))))


def page(db: Session, q: Select, order_by, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(q.with_only_columns(func.count()).order_by(None)) or 0
    return list(db.scalars(q.order_by(*order_by).limit(limit).offset(offset))), total


def _grouped(db: Session, model, parent: str, parent_ids: Iterable[str]) -> dict[str, list[str]]:
    """parent id -> athlete ids, in the order they were given; one query for the whole page."""
    parent_ids = set(parent_ids)
    out: dict[str, list[str]] = defaultdict(list)
    if not parent_ids:
        return out
    column = getattr(model, parent)
    q = query(db, model).where(column.in_(parent_ids)).order_by(column, model.position)
    for row in db.scalars(q):
        out[getattr(row, parent)].append(row.athlete_id)
    return out


def attendees_of(db: Session, session_ids: Iterable[str]) -> dict[str, list[str]]:
    return _grouped(db, SessionAttendee, "session_id", session_ids)


def tagged_athletes_of(db: Session, annotation_ids: Iterable[str]) -> dict[str, list[str]]:
    return _grouped(db, AnnotationAthlete, "annotation_id", annotation_ids)


def set_athletes(db: Session, model, parent: str, parent_id: str, organisation_id: str, athlete_ids: list[str]):
    db.execute(delete(model).where(getattr(model, parent) == parent_id, model.organisation_id == organisation_id))
    for i, athlete_id in enumerate(athlete_ids):
        db.add(model(organisation_id=organisation_id, athlete_id=athlete_id, position=i, **{parent: parent_id}))


def sessions_attended_by(db: Session, athlete_ids: set[str]) -> Select:
    """Ids of the sessions these athletes attend, as an organisation-scoped subquery."""
    q = scoped(db, select(SessionAttendee.session_id), SessionAttendee)
    return q.where(SessionAttendee.athlete_id.in_(athlete_ids))


def annotations_tagging(db: Session, athlete_ids: set[str] | None = None) -> Select:
    """Ids of the annotations that tag these athletes (any athlete when None), as an organisation-scoped subquery."""
    q = scoped(db, select(AnnotationAthlete.annotation_id), AnnotationAthlete)
    if athlete_ids is not None:
        q = q.where(AnnotationAthlete.athlete_id.in_(athlete_ids))
    return q


def drill_titles(db: Session, drill_ids: Iterable[str]) -> dict[str, str]:
    ids = set(drill_ids)
    if not ids:
        return {}
    return dict(db.execute(query(db, Drill).with_only_columns(Drill.id, Drill.title).where(Drill.id.in_(ids))).all())


def tags_of(db: Session, video_id: str) -> list[DrillTag]:
    q = query(db, DrillTag).where(DrillTag.video_id == video_id)
    return list(db.scalars(q.order_by(DrillTag.start_timestamp, DrillTag.created_at, DrillTag.id)))


def athletes_of_user(db: Session, user_id: str) -> set[str]:
    q = query(db, AthleteLink).with_only_columns(AthleteLink.athlete_id).where(AthleteLink.user_id == user_id)
    return set(db.scalars(q))


def link_of(db: Session, athlete_id: str) -> AthleteLink | None:
    return first_by(db, AthleteLink, athlete_id=athlete_id)
