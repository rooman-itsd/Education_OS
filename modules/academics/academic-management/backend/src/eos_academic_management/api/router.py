"""HTTP surface of academic-management, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/academic-management. Handlers only map HTTP to the use cases in application/service.py.

Errors follow the repository's current convention (facility-booking, hostel): a use-case refusal becomes
HTTPException(status, {code, message, details}), which FastAPI wraps as {"detail": ...}. The shared error format is
pending a cross-module decision; no module-specific format is introduced here."""

from __future__ import annotations

from collections.abc import Callable

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as k
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import AcademicManagementError
from ..application.faculty_load import faculty_load_report
from ..infrastructure.config import load_settings
from . import schemas as s
from .deps import require

router = APIRouter(tags=["academic-management"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AcademicManagementError as e:
        raise HTTPException(e.status, e.body()) from e


def faculty_directory() -> Callable[[str], str]:
    """Display names of faculty members (platform/identity users). No identity lookup is available to modules yet
    (packages/sdk is empty and identity exposes no user lookup), so the default refuses when a name is needed
    instead of showing ids as names. The host overrides this dependency once the lookup exists."""

    def unavailable(faculty_id: str) -> str:
        raise AcademicManagementError(
            503, "faculty_directory_unavailable", "faculty names cannot be resolved until the identity lookup exists"
        )

    return unavailable


# ---------------------------------------------------------------- terms


@router.get("/terms")
def list_terms(
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.TERM_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_terms(db, status, limit, offset)


@router.post("/terms", status_code=201)
def create_term(body: s.CreateTermIn, a: Actor = Depends(require(k.TERM_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_term, db, a, s.dump(body))


@router.get("/terms/{academic_period_id}")
def get_term(academic_period_id: str, _: Actor = Depends(require(k.TERM_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_term, db, academic_period_id)


@router.patch("/terms/{academic_period_id}")
def update_term(
    academic_period_id: str,
    body: s.UpdateTermIn,
    a: Actor = Depends(require(k.TERM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_term, db, a, academic_period_id, s.dump(body, partial=True))


@router.post("/terms/{academic_period_id}/activate")
def activate_term(academic_period_id: str, a: Actor = Depends(require(k.TERM_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.activate_term, db, a, academic_period_id)


# ---------------------------------------------------------------- programmes and curricula


@router.get("/programmes")
def list_programmes(
    department_id: str | None = None,
    level: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.PROGRAMME_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_programmes(db, {"department_id": department_id, "level": level, "status": status}, limit, offset)


@router.post("/programmes", status_code=201)
def create_programme(
    body: s.CreateProgrammeIn, a: Actor = Depends(require(k.PROGRAMME_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_programme, db, a, s.dump(body))


@router.get("/programmes/{programme_id}")
def get_programme(programme_id: str, _: Actor = Depends(require(k.PROGRAMME_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_programme, db, programme_id)


@router.patch("/programmes/{programme_id}")
def update_programme(
    programme_id: str,
    body: s.UpdateProgrammeIn,
    a: Actor = Depends(require(k.PROGRAMME_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_programme, db, a, programme_id, s.dump(body, partial=True))


@router.post("/programmes/{programme_id}/archive")
def archive_programme(programme_id: str, a: Actor = Depends(require(k.PROGRAMME_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.archive_programme, db, a, programme_id)


@router.get("/programmes/{programme_id}/curricula")
def list_curricula(
    programme_id: str,
    status: str | None = None,
    _: Actor = Depends(require(k.CURRICULUM_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_curricula, db, programme_id, status)


@router.post("/programmes/{programme_id}/curricula", status_code=201)
def create_curriculum(
    programme_id: str,
    body: s.CreateCurriculumIn,
    a: Actor = Depends(require(k.CURRICULUM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_curriculum, db, a, programme_id, s.dump(body, partial=True))


@router.get("/curricula/{curriculum_id}")
def get_curriculum(curriculum_id: str, _: Actor = Depends(require(k.CURRICULUM_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_curriculum, db, curriculum_id)


@router.put("/curricula/{curriculum_id}")
def replace_curriculum_items(
    curriculum_id: str,
    body: s.ReplaceCurriculumItemsIn,
    a: Actor = Depends(require(k.CURRICULUM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.replace_curriculum_items, db, a, curriculum_id, s.dump(body))


@router.post("/curricula/{curriculum_id}/publish")
def publish_curriculum(
    curriculum_id: str, a: Actor = Depends(require(k.CURRICULUM_PUBLISH)), db: Session = Depends(get_db)
):
    return _run(svc.publish_curriculum, db, a, curriculum_id)


# ---------------------------------------------------------------- courses


@router.get("/courses")
def list_courses(
    department_id: str | None = None,
    course_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.COURSE_READ)),
    db: Session = Depends(get_db),
):
    filters = {"department_id": department_id, "course_type": course_type, "status": status, "q": q}
    return svc.list_courses(db, filters, limit, offset)


@router.post("/courses", status_code=201)
def create_course(body: s.CreateCourseIn, a: Actor = Depends(require(k.COURSE_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_course, db, a, s.dump(body))


@router.get("/courses/{course_id}")
def get_course(course_id: str, _: Actor = Depends(require(k.COURSE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_course, db, course_id)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: str, body: s.UpdateCourseIn, a: Actor = Depends(require(k.COURSE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_course, db, a, course_id, s.dump(body, partial=True))


@router.post("/courses/{course_id}/archive")
def archive_course(course_id: str, a: Actor = Depends(require(k.COURSE_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.archive_course, db, a, course_id)


# ---------------------------------------------------------------- offerings and sections


@router.get("/offerings")
def list_offerings(
    academic_period_id: str | None = None,
    course_id: str | None = None,
    programme_id: str | None = None,
    department_id: str | None = None,
    faculty_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.OFFERING_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "academic_period_id": academic_period_id,
        "course_id": course_id,
        "programme_id": programme_id,
        "department_id": department_id,
        "faculty_id": faculty_id,
        "status": status,
    }
    return svc.list_offerings(db, filters, limit, offset)


@router.post("/offerings", status_code=201)
def create_offering(
    body: s.CreateOfferingIn, a: Actor = Depends(require(k.OFFERING_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_offering, db, a, s.dump(body))


@router.get("/offerings/{course_offering_id}")
def get_offering(course_offering_id: str, _: Actor = Depends(require(k.OFFERING_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_offering, db, course_offering_id)


@router.patch("/offerings/{course_offering_id}")
def update_offering(
    course_offering_id: str,
    body: s.UpdateOfferingIn,
    a: Actor = Depends(require(k.OFFERING_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_offering, db, a, course_offering_id, s.dump(body, partial=True))


@router.post("/offerings/{course_offering_id}/status")
def change_offering_status(
    course_offering_id: str,
    body: s.ChangeOfferingStatusIn,
    a: Actor = Depends(require(k.OFFERING_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.change_offering_status, db, a, course_offering_id, s.dump(body))


@router.get("/offerings/{course_offering_id}/sections")
def list_sections(course_offering_id: str, _: Actor = Depends(require(k.OFFERING_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_sections, db, course_offering_id)


@router.post("/offerings/{course_offering_id}/sections", status_code=201)
def create_section(
    course_offering_id: str,
    body: s.CreateSectionIn,
    a: Actor = Depends(require(k.OFFERING_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_section, db, a, course_offering_id, s.dump(body))


@router.patch("/sections/{section_id}")
def update_section(
    section_id: str,
    body: s.UpdateSectionIn,
    a: Actor = Depends(require(k.OFFERING_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_section, db, a, section_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- faculty assignment


@router.get("/offerings/{course_offering_id}/faculty-assignments")
def list_faculty_assignments(
    course_offering_id: str,
    include_ended: bool = False,
    _: Actor = Depends(require(k.FACULTY_ASSIGNMENT_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_assignments, db, course_offering_id, include_ended)


@router.post("/offerings/{course_offering_id}/faculty-assignments", status_code=201)
def create_faculty_assignment(
    course_offering_id: str,
    body: s.CreateFacultyAssignmentIn,
    a: Actor = Depends(require(k.FACULTY_ASSIGNMENT_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_assignment, db, a, course_offering_id, s.dump(body))


@router.post("/faculty-assignments/{instructor_assignment_id}/end")
def end_faculty_assignment(
    instructor_assignment_id: str,
    a: Actor = Depends(require(k.FACULTY_ASSIGNMENT_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.end_assignment, db, a, instructor_assignment_id)


# ---------------------------------------------------------------- roster, my offerings, faculty load


@router.get("/offerings/{course_offering_id}/roster")
def get_roster(
    course_offering_id: str,
    section_id: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(k.ROSTER_READ, k.ROSTER_READ_ALL)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_roster, db, a, course_offering_id, section_id, limit, offset)


@router.get("/me/offerings")
def list_my_offerings(
    academic_period_id: str | None = None,
    a: Actor = Depends(require(k.ROSTER_READ, k.ROSTER_READ_ALL)),
    db: Session = Depends(get_db),
):
    return svc.list_my_offerings(db, a, academic_period_id)


@router.get("/faculty-load", response_model=s.FacultyLoadReportOut, response_model_exclude_none=False)
def get_faculty_load(
    academic_period_id: str | None = Query(None, pattern=s.UUID),
    department_id: str | None = Query(None, pattern=s.UUID),
    over_load_only: bool = False,
    a: Actor = Depends(require(k.FACULTY_LOAD_READ)),
    db: Session = Depends(get_db),
    names: Callable[[str], str] = Depends(faculty_directory),
):
    """department_id narrows the report; it is never proof of access. Access is the faculty-load:read key alone,
    because no trusted department claim exists yet."""
    period, entries = svc.faculty_load_inputs(db, academic_period_id, department_id)
    return _run(
        faculty_load_report,
        a,
        period=period,
        entries=entries,
        faculty_name=names,
        max_weekly_contact_hours=load_settings().max_weekly_contact_hours,
        department_id=department_id,
        over_load_only=over_load_only,
    )
