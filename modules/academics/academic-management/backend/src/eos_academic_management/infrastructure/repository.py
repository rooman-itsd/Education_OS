"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
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


def programmes_by_id(db: Session, programme_ids) -> dict[str, ProgrammeRow]:
    ids = set(programme_ids)
    if not ids:
        return {}
    return {p.id: p for p in db.scalars(q(db, ProgrammeRow).where(ProgrammeRow.id.in_(ids)))}


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


def section_for_update(db: Session, section_id: str) -> SectionRow | None:
    """Lock the section row so registrations into one section run one after the other (capacity check, PRD FR-10).
    On SQLite FOR UPDATE is a no-op; there writers are serialised by the database lock instead."""
    return db.scalars(section_lock_query(db, section_id)).first()


def section_lock_query(db: Session, section_id: str) -> Select:
    return q(db, SectionRow).where(SectionRow.id == section_id).with_for_update()


def enrolled_in_section(db: Session, section_id: str) -> int:
    query = scoped(db, select(func.count()), RosterEntryRow).where(
        RosterEntryRow.section_id == section_id, RosterEntryRow.status == ENROLLED
    )
    return db.scalar(query) or 0


# Unique constraints that protect a code (contract Conflict, "duplicate code"), by name and by their columns.
CODE_CONSTRAINTS = {
    "uq_academic_management_term_code": ("academic_management_term", ("organisation_id", "code")),
    "uq_academic_management_programme_code": ("academic_management_programme", ("organisation_id", "code")),
    "uq_academic_management_course_code": ("academic_management_course", ("organisation_id", "code")),
    "uq_academic_management_section_code": (
        "academic_management_section",
        ("organisation_id", "course_offering_id", "code"),
    ),
}
# The constraint that numbers curriculum versions of one programme (contract `version`, FR-4).
VERSION_CONSTRAINTS = {
    "uq_academic_management_curriculum_version": (
        "academic_management_curriculum",
        ("organisation_id", "programme_id", "version"),
    ),
}


def _violates(err: IntegrityError, constraints: dict[str, tuple[str, tuple[str, ...]]]) -> bool:
    """True only when `err` is a violation of one of `constraints`. PostgreSQL names the constraint (psycopg
    `diag.constraint_name`); SQLite names its columns ("UNIQUE constraint failed: t.a, t.b"). Any other integrity
    error (another constraint, a foreign key, a NOT NULL) does not count."""
    orig = err.orig
    name = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if name:
        return name in constraints
    message = str(orig)
    return any(
        message == "UNIQUE constraint failed: " + ", ".join(f"{table}.{column}" for column in columns)
        for table, columns in constraints.values()
    )


def is_code_conflict(err: IntegrityError) -> bool:
    """A duplicate code (contract Conflict), and nothing else."""
    return _violates(err, CODE_CONSTRAINTS)


def is_version_conflict(err: IntegrityError) -> bool:
    """Two concurrent creates numbered a programme's curriculum the same, and nothing else."""
    return _violates(err, VERSION_CONSTRAINTS)
