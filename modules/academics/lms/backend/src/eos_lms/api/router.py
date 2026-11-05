"""HTTP surface of lms, as described in contracts/openapi.yaml. The host app mounts `router` under /api/v1/lms.
Handlers only map HTTP to the use cases in application/; each declares the one permission key (x-permission) the
contract names for it, and the use case narrows the scope (application/access.py).

Errors follow the repository's convention: a refusal becomes HTTPException(status, {code, message, details}), which
FastAPI wraps as {"detail": ...}. Request bodies and query parameters are read raw and checked here (schemas.py), so a
malformed one is the contract's 400 with a code, never FastAPI's 422, and never a 500."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..application import access as k
from ..application import content, coursework, discussions, grades, quizzes, reports
from ..application.access import Actor
from ..application.errors import LmsError, invalid
from . import schemas as s
from .deps import require

router = APIRouter(tags=["lms"])

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MAX_OFFSET = 1_000_000
NO_BODY: Any = Body(None)


def _run(call):
    try:
        return call()
    except LmsError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- query parameters


def q_uuid(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not UUID.match(value):
        raise invalid("invalid_parameter", f"{name} must be a uuid", field=name)
    return value


def q_int(value: str | None, name: str, default: int, low: int, high: int) -> int:
    """ASCII digits only, within the contract's bounds."""
    if value is None:
        return default
    if not (value.isascii() and value.isdigit() and len(value) <= 9) or not low <= int(value) <= high:
        raise invalid("invalid_parameter", f"{name} must be a whole number from {low} to {high}", field=name)
    return int(value)


def q_enum(value: str | None, name: str, allowed: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        raise invalid("invalid_parameter", f"{name} must be one of {', '.join(allowed)}", field=name)
    return value


def q_bool(value: str | None, name: str) -> bool:
    if value is None:
        return False
    if value.lower() not in ("true", "false", "1", "0"):
        raise invalid("invalid_parameter", f"{name} must be true or false", field=name)
    return value.lower() in ("true", "1")


def q_instant(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        if not value.isascii() or len(value) > 40:
            raise ValueError
        parsed = s.in_range(datetime.fromisoformat(value.replace(" ", "+")))
    except ValueError:
        raise invalid(
            "invalid_parameter", f"{name} must be a date-time between the years 1900 and 9998", field=name
        ) from None
    return parsed.astimezone(UTC)


def limit_offset(limit: str | None, offset: str | None) -> tuple[int, int]:
    return q_int(limit, "limit", 50, 1, 200), q_int(offset, "offset", 0, 0, MAX_OFFSET)


# ---------------------------------------------------------------- course spaces


@router.get("/course-spaces")
def list_course_spaces(
    course_offering_id: str | None = None,
    department_id: str | None = None,
    status: str | None = None,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    def call():
        filters = {
            "course_offering_id": q_uuid(course_offering_id, "course_offering_id"),
            "department_id": q_uuid(department_id, "department_id"),
            "status": q_enum(status, "status", ("draft", "active", "archived")),
        }
        return content.list_spaces(db, a, filters, *limit_offset(limit, offset))

    return _run(call)


@router.post("/course-spaces", status_code=201)
def create_course_space(
    body: Any = NO_BODY, a: Actor = Depends(require(k.COURSE_SPACE_MANAGE_ALL)), db: Session = Depends(get_db)
):
    return _run(lambda: content.create_space(db, a, s.parse(s.CreateCourseSpaceIn, body)))


@router.get("/course-spaces/{course_space_id}")
def get_course_space(
    course_space_id: str, a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: content.get_space(db, a, course_space_id))


@router.patch("/course-spaces/{course_space_id}")
def update_course_space(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.COURSE_SPACE_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.update_space(db, a, course_space_id, s.parse(s.UpdateCourseSpaceIn, body)))


@router.post("/course-spaces/{course_space_id}/status")
def change_course_space_status(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.COURSE_SPACE_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: content.change_space_status(db, a, course_space_id, s.parse(s.CourseSpaceStatusIn, body)["status"])
    )


# ---------------------------------------------------------------- content units


@router.get("/course-spaces/{course_space_id}/units")
def list_content_units(
    course_space_id: str, a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: content.list_units(db, a, course_space_id))


@router.post("/course-spaces/{course_space_id}/units", status_code=201)
def create_content_unit(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.MATERIAL_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.create_unit(db, a, course_space_id, s.parse(s.ContentUnitIn, body)))


@router.patch("/units/{unit_id}")
def update_content_unit(
    unit_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.MATERIAL_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.update_unit(db, a, unit_id, s.parse(s.UpdateContentUnitIn, body)))


# ---------------------------------------------------------------- materials


@router.get("/course-spaces/{course_space_id}/materials")
def list_course_materials(
    course_space_id: str,
    unit_id: str | None = None,
    material_type: str | None = None,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    def call():
        filters = {
            "unit_id": q_uuid(unit_id, "unit_id"),
            "material_type": q_enum(material_type, "material_type", ("document", "link", "page")),
        }
        return content.list_materials(db, a, course_space_id, filters, *limit_offset(limit, offset))

    return _run(call)


@router.post("/course-spaces/{course_space_id}/materials", status_code=201)
def create_course_material(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.MATERIAL_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.create_material(db, a, course_space_id, s.parse(s.CourseMaterialIn, body)))


@router.get("/materials/{material_id}")
def get_course_material(
    material_id: str, a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: content.get_material(db, a, material_id))


@router.patch("/materials/{material_id}")
def update_course_material(
    material_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.MATERIAL_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.update_material(db, a, material_id, s.parse(s.UpdateCourseMaterialIn, body)))


@router.post("/materials/{material_id}/status")
def change_course_material_status(
    material_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.MATERIAL_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.change_material_status(db, a, material_id, s.parse(s.MaterialStatusIn, body)["status"]))


# ---------------------------------------------------------------- assignments and submissions

WORK_STATUSES = ("draft", "published", "closed")


@router.get("/course-spaces/{course_space_id}/assignments")
def list_assignments(
    course_space_id: str,
    status: str | None = None,
    unit_id: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: coursework.list_assignments(
            db, a, course_space_id, q_enum(status, "status", WORK_STATUSES), q_uuid(unit_id, "unit_id")
        )
    )


@router.post("/course-spaces/{course_space_id}/assignments", status_code=201)
def create_assignment(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.ASSIGNMENT_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: coursework.create_assignment(db, a, course_space_id, s.parse(s.AssignmentIn, body)))


@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment_id: str, a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: coursework.get_assignment(db, a, assignment_id))


@router.patch("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.ASSIGNMENT_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: coursework.update_assignment(db, a, assignment_id, s.parse(s.UpdateAssignmentIn, body)))


@router.post("/assignments/{assignment_id}/status")
def change_assignment_status(
    assignment_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.ASSIGNMENT_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: coursework.change_assignment_status(db, a, assignment_id, s.parse(s.WorkStatusIn, body)["status"])
    )


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(
    assignment_id: str,
    status: str | None = None,
    include_superseded: str | None = None,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.SUBMISSION_READ_ASSIGNED)),
    db: Session = Depends(get_db),
):
    def call():
        filters = {
            "status": q_enum(status, "status", ("submitted", "graded", "superseded")),
            "include_superseded": q_bool(include_superseded, "include_superseded"),
        }
        if filters["status"] == "superseded":
            filters["include_superseded"] = True
        return coursework.list_submissions(db, a, assignment_id, filters, *limit_offset(limit, offset))

    return _run(call)


@router.post("/assignments/{assignment_id}/submissions", status_code=201)
def submit_assignment(
    assignment_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.SUBMISSION_SUBMIT_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: coursework.submit(db, a, assignment_id, s.parse(s.SubmissionIn, body)))


# ---------------------------------------------------------------- quizzes and attempts


@router.get("/course-spaces/{course_space_id}/quizzes")
def list_quizzes(
    course_space_id: str,
    status: str | None = None,
    unit_id: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: quizzes.list_quizzes(
            db, a, course_space_id, q_enum(status, "status", WORK_STATUSES), q_uuid(unit_id, "unit_id")
        )
    )


@router.post("/course-spaces/{course_space_id}/quizzes", status_code=201)
def create_quiz(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.QUIZ_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: quizzes.create_quiz(db, a, course_space_id, s.parse(s.QuizIn, body)))


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: str, a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)), db: Session = Depends(get_db)):
    return _run(lambda: quizzes.get_quiz(db, a, quiz_id))


@router.patch("/quizzes/{quiz_id}")
def update_quiz(
    quiz_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.QUIZ_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: quizzes.update_quiz(db, a, quiz_id, s.parse(s.UpdateQuizIn, body)))


@router.post("/quizzes/{quiz_id}/status")
def change_quiz_status(
    quiz_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.QUIZ_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: quizzes.change_quiz_status(db, a, quiz_id, s.parse(s.WorkStatusIn, body)["status"]))


@router.get("/quizzes/{quiz_id}/attempts")
def list_quiz_attempts(
    quiz_id: str,
    manual_grading_state: str | None = None,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.QUIZ_ATTEMPT_READ_ASSIGNED)),
    db: Session = Depends(get_db),
):
    def call():
        state = q_enum(manual_grading_state, "manual_grading_state", ("none", "pending", "done"))
        return quizzes.list_attempts(db, a, quiz_id, state, *limit_offset(limit, offset))

    return _run(call)


@router.post("/quizzes/{quiz_id}/attempts", status_code=201)
def start_quiz_attempt(
    quiz_id: str, a: Actor = Depends(require(k.QUIZ_ATTEMPT_ATTEMPT_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: quizzes.start_attempt(db, a, quiz_id))


@router.put("/attempts/{attempt_id}/answers")
def save_quiz_answers(
    attempt_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.QUIZ_ATTEMPT_ATTEMPT_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: quizzes.save_answers(db, a, attempt_id, s.parse(s.AnswersIn, body)["answers"]))


@router.post("/attempts/{attempt_id}/submit")
def submit_quiz_attempt(
    attempt_id: str, a: Actor = Depends(require(k.QUIZ_ATTEMPT_ATTEMPT_OWN)), db: Session = Depends(get_db)
):
    return _run(lambda: quizzes.submit_attempt(db, a, attempt_id))


@router.patch("/attempts/{attempt_id}/scores")
def score_quiz_attempt(
    attempt_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.GRADE_MANAGE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: quizzes.score_attempt(db, a, attempt_id, s.parse(s.ScoresIn, body)["scores"]))


# ---------------------------------------------------------------- grades


@router.put("/grades")
def enter_grades(
    body: Any = NO_BODY, a: Actor = Depends(require(k.GRADE_MANAGE_ASSIGNED)), db: Session = Depends(get_db)
):
    return _run(lambda: grades.enter_grades(db, a, s.parse(s.EnterGradesIn, body)))


@router.post("/grades/release")
def release_grades(
    body: Any = NO_BODY, a: Actor = Depends(require(k.GRADE_MANAGE_ASSIGNED)), db: Session = Depends(get_db)
):
    return _run(lambda: grades.release_grades(db, a, s.parse(s.ReleaseGradesIn, body)))


@router.get("/course-spaces/{course_space_id}/gradebook")
def get_gradebook(
    course_space_id: str, a: Actor = Depends(require(k.GRADE_READ_ASSIGNED)), db: Session = Depends(get_db)
):
    return _run(lambda: grades.gradebook(db, a, course_space_id))


# ---------------------------------------------------------------- discussions


@router.get("/course-spaces/{course_space_id}/threads")
def list_threads(
    course_space_id: str,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.list_threads(db, a, course_space_id, *limit_offset(limit, offset)))


@router.post("/course-spaces/{course_space_id}/threads", status_code=201)
def create_thread(
    course_space_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.DISCUSSION_POST_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.create_thread(db, a, course_space_id, s.parse(s.ThreadIn, body)))


@router.get("/threads/{thread_id}")
def get_thread(
    thread_id: str,
    limit: str | None = None,
    offset: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.get_thread(db, a, thread_id, *limit_offset(limit, offset)))


@router.post("/threads/{thread_id}/posts", status_code=201)
def create_post(
    thread_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.DISCUSSION_POST_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.create_post(db, a, thread_id, s.parse(s.PostIn, body)))


@router.post("/threads/{thread_id}/moderation")
def moderate_thread(
    thread_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.DISCUSSION_MODERATE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.moderate_thread(db, a, thread_id, s.parse(s.ThreadModerationIn, body)["action"]))


@router.post("/posts/{post_id}/moderation")
def moderate_post(
    post_id: str,
    body: Any = NO_BODY,
    a: Actor = Depends(require(k.DISCUSSION_MODERATE_ASSIGNED)),
    db: Session = Depends(get_db),
):
    return _run(lambda: discussions.moderate_post(db, a, post_id, s.parse(s.PostModerationIn, body)["action"]))


# ---------------------------------------------------------------- reports


@router.get("/reports/coursework-activity")
def get_coursework_activity_report(
    department_id: str | None = None,
    academic_period_id: str | None = None,
    a: Actor = Depends(require(k.REPORT_READ_DEPARTMENT)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: reports.coursework_activity(
            db, a, q_uuid(department_id, "department_id"), q_uuid(academic_period_id, "academic_period_id")
        )
    )


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/grading-queue")
def get_my_grading_queue(a: Actor = Depends(require(k.GRADE_MANAGE_ASSIGNED)), db: Session = Depends(get_db)):
    return _run(lambda: grades.grading_queue(db, a))


@router.get("/me/course-materials")
def get_my_course_materials(
    since: str | None = None,
    limit: str | None = None,
    a: Actor = Depends(require(k.COURSE_SPACE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: content.my_course_materials(db, a, q_instant(since, "since"), q_int(limit, "limit", 10, 1, 50)))


@router.get("/me/submissions")
def list_my_submissions(
    assignment_id: str | None = None,
    course_space_id: str | None = None,
    a: Actor = Depends(require(k.SUBMISSION_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: coursework.my_submissions(
            db, a, q_uuid(assignment_id, "assignment_id"), q_uuid(course_space_id, "course_space_id")
        )
    )


@router.get("/me/quiz-attempts")
def list_my_quiz_attempts(
    quiz_id: str | None = None,
    course_space_id: str | None = None,
    a: Actor = Depends(require(k.QUIZ_ATTEMPT_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(
        lambda: quizzes.my_attempts(db, a, q_uuid(quiz_id, "quiz_id"), q_uuid(course_space_id, "course_space_id"))
    )


@router.get("/me/grades")
def list_my_grades(
    course_space_id: str | None = None,
    a: Actor = Depends(require(k.GRADE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(lambda: grades.my_grades(db, a, q_uuid(course_space_id, "course_space_id")))
