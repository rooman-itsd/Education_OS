"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath; on SQLite, which has none, `q` is what keeps a query inside the organisation, so no query in
this module is written without it. The use cases that call these are a later slice; this is the scoped base they use."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    AssessmentComponentRow,
    AssessmentSchemeRow,
    AuditEntry,
    ExamCycleRow,
    ExamDutyRow,
    ExamPaperRow,
    ExamSessionPaperRow,
    ExamSessionRow,
    GradingBandRow,
    GradingSchemeRow,
)


def q(db: Session, model) -> Select:
    """`select(model)` limited to the session's organisation. With no organisation on the session it matches nothing."""
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    """One row of the caller's organisation by id, or None (another organisation's row is not found)."""
    return db.scalars(q(db, model).where(model.id == row_id)).first()


# Constraint name -> (table, columns), for telling a conflict the module answers with 409 from any other integrity error.
CONSTRAINTS = {
    "default_grading_scheme": {
        "uq_examinations_grading_scheme_default": ("examinations_grading_scheme", ("organisation_id",)),
    },
    "assessment_scheme_version": {
        "uq_examinations_assessment_scheme_version": (
            "examinations_assessment_scheme",
            ("organisation_id", "course_offering_id", "version"),
        ),
    },
    "active_assessment_scheme": {
        "uq_examinations_assessment_scheme_active": (
            "examinations_assessment_scheme",
            ("organisation_id", "course_offering_id"),
        ),
    },
    "paper_component": {
        "uq_examinations_paper_component": (
            "examinations_exam_paper",
            ("organisation_id", "exam_cycle_id", "assessment_component_id"),
        ),
    },
    "paper_in_session": {
        "uq_examinations_session_paper": ("examinations_session_paper", ("organisation_id", "exam_paper_id")),
    },
    "duty_on_session": {
        "uq_examinations_duty_session_live": (
            "examinations_exam_duty",
            ("organisation_id", "staff_id", "duty_type", "exam_session_id"),
        ),
    },
    "duty_on_paper": {
        "uq_examinations_duty_paper_live": (
            "examinations_exam_duty",
            ("organisation_id", "staff_id", "duty_type", "exam_paper_id"),
        ),
    },
    "audit_token": {
        "uq_examinations_audit_client_token": ("examinations_audit_entry", ("organisation_id", "client_token")),
    },
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


def violates(err: IntegrityError, which: str) -> bool:
    """Whether the integrity error is a violation of the named uniqueness rule in CONSTRAINTS."""
    return _violates(err, CONSTRAINTS[which])


def audit_entry_by_token(db: Session, organisation_id: str, client_token: str) -> AuditEntry | None:
    query = q(db, AuditEntry).where(
        AuditEntry.organisation_id == organisation_id, AuditEntry.client_token == client_token
    )
    return db.scalars(query).first()


# ---------------------------------------------------------------- the lookups the use cases of the next slice start from


def bands_of(db: Session, grading_scheme_id: str) -> list[GradingBandRow]:
    rows = db.scalars(q(db, GradingBandRow).where(GradingBandRow.grading_scheme_id == grading_scheme_id))
    return sorted(rows, key=lambda r: (r.min_percent, r.max_percent, r.id))


def default_grading_scheme(db: Session) -> GradingSchemeRow | None:
    return db.scalars(q(db, GradingSchemeRow).where(GradingSchemeRow.is_default.is_(True))).first()


def schemes_of_offering(db: Session, course_offering_id: str) -> list[AssessmentSchemeRow]:
    rows = db.scalars(q(db, AssessmentSchemeRow).where(AssessmentSchemeRow.course_offering_id == course_offering_id))
    return sorted(rows, key=lambda r: r.version)


def components_of(db: Session, assessment_scheme_id: str) -> list[AssessmentComponentRow]:
    rows = db.scalars(
        q(db, AssessmentComponentRow).where(AssessmentComponentRow.assessment_scheme_id == assessment_scheme_id)
    )
    return sorted(rows, key=lambda r: (r.code, r.id))


def papers_of_cycle(db: Session, exam_cycle_id: str) -> list[ExamPaperRow]:
    rows = db.scalars(q(db, ExamPaperRow).where(ExamPaperRow.exam_cycle_id == exam_cycle_id))
    return sorted(rows, key=lambda r: r.id)


def paper_ids_in_sessions(db: Session, paper_ids: list[str]) -> set[str]:
    """Which of these papers are already in a session."""
    if not paper_ids:
        return set()
    rows = db.scalars(q(db, ExamSessionPaperRow).where(ExamSessionPaperRow.exam_paper_id.in_(paper_ids)))
    return {r.exam_paper_id for r in rows}


def assigned_invigilation_sessions(db: Session, staff_id: str) -> list[ExamSessionRow]:
    """The sessions a staff member invigilates through an assigned duty (FR-9's overlap check starts from these). A
    cancelled session is left out: its duties stay `assigned` (nothing cancels them with it) but it no longer takes the
    staff member's time."""
    query = (
        q(db, ExamSessionRow)
        .join(ExamDutyRow, ExamDutyRow.exam_session_id == ExamSessionRow.id)
        .where(
            ExamSessionRow.status != "cancelled",
            ExamDutyRow.staff_id == staff_id,
            ExamDutyRow.duty_type == "invigilation",
            ExamDutyRow.status == "assigned",
            ExamDutyRow.organisation_id == ExamSessionRow.organisation_id,
        )
    )
    return sorted(db.scalars(query), key=lambda r: (r.starts_at, r.id))


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(q(db, model).subquery())) or 0


def cycle(db: Session, exam_cycle_id: str) -> ExamCycleRow | None:
    return get(db, ExamCycleRow, exam_cycle_id)


# ---------------------------------------------------------------- listings for the configuration and exam-cycle use cases

PUBLISHED_CYCLE_STATUSES = ("results_published", "closed")  # a cycle whose results were published (PRD section 6)


def page(db: Session, query: Select, order: list, limit: int, offset: int) -> tuple[list, int]:
    """One page of an already-scoped query, ordered, and the total before paging."""
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(query.order_by(*order).limit(limit).offset(offset)))
    return rows, total


def grading_schemes_in_use(db: Session) -> set[str]:
    """Ids of the grading schemes a cycle with published results uses (FR-3: those cannot change)."""
    query = scoped(
        db,
        select(ExamCycleRow.grading_scheme_id).where(ExamCycleRow.status.in_(PUBLISHED_CYCLE_STATUSES)).distinct(),
        ExamCycleRow,
    )
    return set(db.scalars(query))


def grading_scheme_in_use(db: Session, grading_scheme_id: str) -> bool:
    return grading_scheme_id in grading_schemes_in_use(db)


def grading_schemes(db: Session) -> list[GradingSchemeRow]:
    return list(db.scalars(q(db, GradingSchemeRow).order_by(GradingSchemeRow.name, GradingSchemeRow.id)))


# ---------------------------------------------------------------- exam duties

LIVE_DUTY_STATUSES = ("assigned", "completed")  # the statuses the unique indexes of ex_0003 cover


def duty(db: Session, exam_duty_id: str) -> ExamDutyRow | None:
    return get(db, ExamDutyRow, exam_duty_id)


def live_duplicate_duty(
    db: Session, staff_id: str, duty_type: str, exam_session_id: str | None, exam_paper_id: str | None
) -> ExamDutyRow | None:
    """The assigned or completed duty of this staff member and type on the same target, if any."""
    query = q(db, ExamDutyRow).where(
        ExamDutyRow.staff_id == staff_id,
        ExamDutyRow.duty_type == duty_type,
        ExamDutyRow.status.in_(LIVE_DUTY_STATUSES),
    )
    if exam_session_id is not None:
        query = query.where(ExamDutyRow.exam_session_id == exam_session_id)
    else:
        query = query.where(ExamDutyRow.exam_paper_id == exam_paper_id)
    return db.scalars(query).first()


def duties_of_staff(db: Session, staff_id: str, status: str) -> list[ExamDutyRow]:
    rows = db.scalars(q(db, ExamDutyRow).where(ExamDutyRow.staff_id == staff_id, ExamDutyRow.status == status))
    return sorted(rows, key=lambda r: (r.created_at, r.id))
