"""Routes from contracts/openapi.yaml, mounted by the host at /api/v1/enrolment-registration. Each route names the
permission key it needs; the service filters every query by the caller's organisation."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, EnrolmentError
from . import schemas as s
from .deps import (
    PERM_ENROLMENT_MANAGE,
    PERM_ENROLMENT_READ,
    PERM_REGISTRATION_MANAGE,
    PERM_REGISTRATION_READ,
    require,
)

router = APIRouter(tags=["enrolment-registration"])

Page = Query(1, ge=1)
PageSize = Query(50, ge=1, le=200)


def _run(db: Session, fn, *args: Any, conflict: tuple[str, str] | None = None, **kwargs: Any) -> Any:
    """Run a use case, commit, and turn refusals into the contract's {code, message} error body."""
    try:
        result = fn(db, *args, **kwargs)
        db.commit()
        return result
    except EnrolmentError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.to_dict()) from exc
    except IntegrityError as exc:
        # Two requests passed the same check at once; a unique index decided.
        db.rollback()
        code, message = conflict or ("conflict", "a record with the same unique value already exists")
        raise HTTPException(409, {"code": code, "message": message}) from exc


def _s(value: UUID | None) -> str | None:
    return str(value) if value else None


# ---------------------------------------------------------------- programme enrolment


@router.get("/programme-enrolments")
def list_enrolments(
    programme_id: UUID | None = None,
    person_id: UUID | None = None,
    status: Literal["active", "completed", "withdrawn"] | None = None,
    q: str | None = None,
    page: int = Page,
    page_size: int = PageSize,
    actor: Actor = Depends(require(PERM_ENROLMENT_READ)),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.list_enrolments,
        actor,
        programme_id=_s(programme_id),
        person_id=_s(person_id),
        status=status,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.post("/programme-enrolments", status_code=201)
def create_enrolment(
    body: s.EnrolmentInput, actor: Actor = Depends(require(PERM_ENROLMENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(
        db,
        svc.enrol,
        actor,
        person_id=str(body.person_id),
        student_name=body.student_name,
        programme_id=str(body.programme_id),
        start_academic_period_id=str(body.start_academic_period_id),
        source_application_id=_s(body.source_application_id),
        conflict=("duplicate_enrolment", "The person already has an active enrolment in this programme"),
    )


@router.get("/programme-enrolments/{programme_enrolment_id}")
def get_enrolment(
    programme_enrolment_id: str, actor: Actor = Depends(require(PERM_ENROLMENT_READ)), db: Session = Depends(get_db)
):
    return _run(db, svc.get_enrolment, actor, programme_enrolment_id)


@router.post("/programme-enrolments/{programme_enrolment_id}/withdraw")
def withdraw_enrolment(
    programme_enrolment_id: str,
    body: s.ReasonInput,
    actor: Actor = Depends(require(PERM_ENROLMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.withdraw_enrolment, actor, programme_enrolment_id, body.reason)


@router.post("/programme-enrolments/{programme_enrolment_id}/complete")
def complete_enrolment(
    programme_enrolment_id: str, actor: Actor = Depends(require(PERM_ENROLMENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(db, svc.complete_enrolment, actor, programme_enrolment_id)


# ---------------------------------------------------------------- registration windows


@router.get("/terms/{academic_period_id}/registration-window")
def get_window(
    academic_period_id: UUID, actor: Actor = Depends(require(PERM_REGISTRATION_READ)), db: Session = Depends(get_db)
):
    return _run(db, svc.get_window, actor, str(academic_period_id))


@router.put("/terms/{academic_period_id}/registration-window")
def set_window(
    academic_period_id: UUID,
    body: s.WindowInput,
    actor: Actor = Depends(require(PERM_REGISTRATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.set_window, actor, str(academic_period_id), body.opens_at, body.closes_at)


# ---------------------------------------------------------------- course registration


@router.get("/registrations")
def list_registrations(
    academic_period_id: UUID | None = None,
    course_offering_id: UUID | None = None,
    section_id: UUID | None = None,
    person_id: UUID | None = None,
    programme_enrolment_id: UUID | None = None,
    registration_type: Literal["regular", "supplementary", "backlog"] | None = None,
    status: Literal["confirmed", "withdrawn"] | None = None,
    page: int = Page,
    page_size: int = PageSize,
    actor: Actor = Depends(require(PERM_REGISTRATION_READ)),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.list_registrations,
        actor,
        academic_period_id=_s(academic_period_id),
        course_offering_id=_s(course_offering_id),
        section_id=_s(section_id),
        person_id=_s(person_id),
        programme_enrolment_id=_s(programme_enrolment_id),
        registration_type=registration_type,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("/registrations", status_code=201)
def register(
    body: s.RegistrationInput, actor: Actor = Depends(require(PERM_REGISTRATION_MANAGE)), db: Session = Depends(get_db)
):
    return _run(
        db,
        svc.register,
        actor,
        programme_enrolment_id=str(body.programme_enrolment_id),
        course_offering_id=str(body.course_offering_id),
        section_id=str(body.section_id),
        academic_period_id=str(body.academic_period_id),
        registration_type=body.registration_type,
        conflict=("already_registered", "The student already has a confirmed registration for this offering"),
    )


@router.post("/registrations/bulk")
def register_bulk(
    body: s.BulkRegistrationInput,
    actor: Actor = Depends(require(PERM_REGISTRATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.register_bulk,
        actor,
        programme_enrolment_ids=body.unique_ids(),
        course_offering_id=str(body.course_offering_id),
        section_id=str(body.section_id),
        academic_period_id=str(body.academic_period_id),
        registration_type=body.registration_type,
    )


@router.get("/registrations/{registration_id}")
def get_registration(
    registration_id: str, actor: Actor = Depends(require(PERM_REGISTRATION_READ)), db: Session = Depends(get_db)
):
    return _run(db, svc.get_registration, actor, registration_id)


@router.post("/registrations/{registration_id}/withdraw")
def withdraw_registration(
    registration_id: str,
    body: s.ReasonInput,
    actor: Actor = Depends(require(PERM_REGISTRATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.withdraw_registration, actor, registration_id, body.reason)


@router.post("/registrations/{registration_id}/change-section")
def change_section(
    registration_id: str,
    body: s.SectionChangeInput,
    actor: Actor = Depends(require(PERM_REGISTRATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.change_section, actor, registration_id, str(body.to_section_id), body.effective_on)


# ---------------------------------------------------------------- widgets


@router.get("/reports/registered-candidates")
def registered_candidates(
    academic_period_id: UUID | None = None,
    limit: int = Query(5, ge=1, le=50),
    actor: Actor = Depends(require(PERM_REGISTRATION_READ)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.registered_candidates, actor, academic_period_id=_s(academic_period_id), limit=limit)
