"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import (
    CourseRow,
    CurriculumItemRow,
    CurriculumRow,
    FacultyAssignmentRow,
    OfferingRow,
    ProcessedEventRow,
    ProgrammeRow,
    RosterEntryRow,
    SectionRow,
    TermRow,
)

ENROLLED, WITHDRAWN = "enrolled", "withdrawn"


def q(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(q(db, model).where(model.id == row_id)).first()


def page(db: Session, query: Select, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    return list(db.scalars(query.limit(limit).offset(offset))), total


def codes(db: Session, model) -> list[str]:
    return list(db.scalars(q(db, model).with_only_columns(model.code)))


def terms(db: Session) -> list[TermRow]:
    return list(db.scalars(q(db, TermRow).order_by(TermRow.starts_on)))


def active_term(db: Session) -> TermRow | None:
    return db.scalars(q(db, TermRow).where(TermRow.status == "active")).first()


def curricula_of(db: Session, programme_id: str) -> list[CurriculumRow]:
    return list(db.scalars(q(db, CurriculumRow).where(CurriculumRow.programme_id == programme_id)))


def curriculum_items(db: Session, curriculum_id: str) -> list[CurriculumItemRow]:
    query = q(db, CurriculumItemRow).where(CurriculumItemRow.curriculum_id == curriculum_id)
    return list(db.scalars(query.order_by(CurriculumItemRow.programme_term, CurriculumItemRow.id)))


def courses_by_id(db: Session, course_ids) -> dict[str, CourseRow]:
    ids = set(course_ids)
    if not ids:
        return {}
    return {c.id: c for c in db.scalars(q(db, CourseRow).where(CourseRow.id.in_(ids)))}


def sections_of(db: Session, offering_id: str) -> list[SectionRow]:
    query = q(db, SectionRow).where(SectionRow.course_offering_id == offering_id)
    return list(db.scalars(query.order_by(SectionRow.code)))


def assignments_of(db: Session, offering_id: str, include_ended: bool = True) -> list[FacultyAssignmentRow]:
    query = q(db, FacultyAssignmentRow).where(FacultyAssignmentRow.course_offering_id == offering_id)
    if not include_ended:
        query = query.where(FacultyAssignmentRow.status == "active")
    return list(db.scalars(query.order_by(FacultyAssignmentRow.created_at, FacultyAssignmentRow.id)))


def active_assignments_of_faculty(db: Session, faculty_id: str) -> list[FacultyAssignmentRow]:
    query = q(db, FacultyAssignmentRow).where(
        FacultyAssignmentRow.faculty_id == faculty_id, FacultyAssignmentRow.status == "active"
    )
    return list(db.scalars(query))


def enrolled_counts(db: Session, offering_id: str) -> dict[str, int]:
    """Enrolled students per section of one offering."""
    query = (
        scoped(db, select(RosterEntryRow.section_id, func.count()), RosterEntryRow)
        .where(RosterEntryRow.course_offering_id == offering_id, RosterEntryRow.status == ENROLLED)
        .group_by(RosterEntryRow.section_id)
    )
    return {section_id: n for section_id, n in db.execute(query)}


def roster_entry(db: Session, registration_id: str) -> RosterEntryRow | None:
    return db.scalars(q(db, RosterEntryRow).where(RosterEntryRow.registration_id == registration_id)).first()


def processed(db: Session, event_id: str) -> ProcessedEventRow | None:
    return db.scalars(q(db, ProcessedEventRow).where(ProcessedEventRow.event_id == event_id)).first()


def programme(db: Session, programme_id: str) -> ProgrammeRow | None:
    return get(db, ProgrammeRow, programme_id)


def offering(db: Session, offering_id: str) -> OfferingRow | None:
    return get(db, OfferingRow, offering_id)
