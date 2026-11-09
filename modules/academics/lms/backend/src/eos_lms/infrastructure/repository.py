"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

from collections.abc import Collection

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .models import (
    Assignment,
    ContentUnit,
    CourseMaterial,
    CourseSpace,
    DiscussionPost,
    DiscussionThread,
    Grade,
    InstructorRef,
    MemberRef,
    OfferingRef,
    PersonAccount,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Submission,
)


def q(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def _is(column, value: str | Collection[str]):
    """column equals the id, or is one of the ids (a learner's person id and user id, common.learner_ids)."""
    if isinstance(value, str):
        return column == value
    return column.in_(sorted(value))


def get(db: Session, model, row_id: str):
    return db.scalars(q(db, model).where(model.id == row_id)).first()


def get_for_update(db: Session, model, row_id: str):
    """The row, locked for the rest of the transaction on Postgres (SQLite runs one writer at a time)."""
    return db.scalars(q(db, model).where(model.id == row_id).with_for_update()).first()


def count(db: Session, query: Select) -> int:
    return db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0


# ---------------------------------------------------------------- read models and membership


def ref_row(db: Session, model, column, value: str, organisation_id: str):
    """A read-model row by its natural key, in one organisation (consumers name the organisation explicitly)."""
    return db.scalars(
        q(db, model).where(column == value, model.organisation_id == organisation_id).with_for_update()
    ).first()


def offering(db: Session, offering_id: str) -> OfferingRef | None:
    return db.scalars(q(db, OfferingRef).where(OfferingRef.course_offering_id == offering_id)).first()


def offerings(db: Session, offering_ids: set[str]) -> dict[str, OfferingRef]:
    if not offering_ids:
        return {}
    rows = db.scalars(q(db, OfferingRef).where(OfferingRef.course_offering_id.in_(sorted(offering_ids))))
    return {r.course_offering_id: r for r in rows}


def taught_offerings(db: Session, user_id: str) -> set[str]:
    rows = db.scalars(
        q(db, InstructorRef).where(InstructorRef.instructor_id == user_id, InstructorRef.status == "active")
    )
    return {r.course_offering_id for r in rows}


def person_for_user(db: Session, user_id: str) -> str | None:
    """The student-information person a sign-in account is linked to, if a link is known. Two persons can briefly claim
    one account when the events arrive out of order; the later link wins."""
    query = q(db, PersonAccount).where(PersonAccount.identity_user_id == user_id)
    row = db.scalars(query.order_by(PersonAccount.linked_as_of.desc(), PersonAccount.id)).first()
    return row.person_id if row is not None else None


def registrations(db: Session, student_ids: str | Collection[str]) -> dict[str, set[str | None]]:
    """Course offering -> the sections the student is registered in (None when no section is known)."""
    out: dict[str, set[str | None]] = {}
    for r in db.scalars(q(db, MemberRef).where(_is(MemberRef.student_id, student_ids), MemberRef.status == "active")):
        out.setdefault(r.course_offering_id, set()).add(r.section_id)
    return out


def members(db: Session, offering_id: str) -> list[MemberRef]:
    query = q(db, MemberRef).where(MemberRef.course_offering_id == offering_id, MemberRef.status == "active")
    return list(db.scalars(query.order_by(MemberRef.student_name, MemberRef.student_id)))


def member_names(db: Session, offering_id: str) -> dict[str, str | None]:
    rows = db.scalars(q(db, MemberRef).where(MemberRef.course_offering_id == offering_id))
    return {r.student_id: r.student_name for r in rows}


# ---------------------------------------------------------------- course spaces and content


def space_by_offering(db: Session, offering_id: str) -> CourseSpace | None:
    return db.scalars(q(db, CourseSpace).where(CourseSpace.course_offering_id == offering_id)).first()


def spaces_query(db: Session, filters: dict) -> Select:
    query = q(db, CourseSpace)
    if filters.get("course_offering_id"):
        query = query.where(CourseSpace.course_offering_id == filters["course_offering_id"])
    if filters.get("department_id"):
        query = query.where(CourseSpace.department_id == filters["department_id"])
    if filters.get("status"):
        query = query.where(CourseSpace.status == filters["status"])
    if filters.get("offering_ids") is not None:
        query = query.where(CourseSpace.course_offering_id.in_(sorted(filters["offering_ids"])))
    return query.order_by(CourseSpace.title, CourseSpace.id)


def spaces_for_offerings(db: Session, offering_ids: set[str]) -> list[CourseSpace]:
    if not offering_ids:
        return []
    query = q(db, CourseSpace).where(CourseSpace.course_offering_id.in_(sorted(offering_ids)))
    return list(db.scalars(query.order_by(CourseSpace.title, CourseSpace.id)))


def all_spaces(db: Session) -> list[CourseSpace]:
    return list(db.scalars(q(db, CourseSpace).order_by(CourseSpace.title, CourseSpace.id)))


def units(db: Session, space_id: str) -> list[ContentUnit]:
    query = q(db, ContentUnit).where(ContentUnit.course_space_id == space_id)
    return list(db.scalars(query.order_by(ContentUnit.position, ContentUnit.created_at, ContentUnit.id)))


def next_unit_position(db: Session, space_id: str) -> int:
    top = db.scalar(
        scoped(db, select(func.max(ContentUnit.position)), ContentUnit).where(ContentUnit.course_space_id == space_id)
    )
    return 0 if top is None else top + 1


def materials(db: Session, space_ids: list[str], **filters) -> list[CourseMaterial]:
    if not space_ids:
        return []
    query = q(db, CourseMaterial).where(CourseMaterial.course_space_id.in_(space_ids))
    for column in ("unit_id", "material_type", "status"):
        if filters.get(column):
            query = query.where(getattr(CourseMaterial, column) == filters[column])
    if filters.get("published_since") is not None:
        query = query.where(CourseMaterial.published_at >= filters["published_since"])
    return list(db.scalars(query.order_by(CourseMaterial.created_at, CourseMaterial.id)))


def assignments(db: Session, space_ids: list[str]) -> list[Assignment]:
    if not space_ids:
        return []
    query = q(db, Assignment).where(Assignment.course_space_id.in_(space_ids))
    return list(db.scalars(query.order_by(Assignment.due_at, Assignment.id)))


def quizzes(db: Session, space_ids: list[str]) -> list[Quiz]:
    if not space_ids:
        return []
    query = q(db, Quiz).where(Quiz.course_space_id.in_(space_ids))
    return list(db.scalars(query.order_by(Quiz.opens_at, Quiz.id)))


def questions(db: Session, quiz_id: str) -> list[QuizQuestion]:
    query = q(db, QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
    return list(db.scalars(query.order_by(QuizQuestion.position, QuizQuestion.id)))


def question_stats(db: Session, quiz_ids: list[str]) -> dict[str, tuple[int, float]]:
    """Quiz -> (question count, total points)."""
    if not quiz_ids:
        return {}
    query = (
        scoped(db, select(QuizQuestion.quiz_id, func.count(), func.sum(QuizQuestion.points)), QuizQuestion)
        .where(QuizQuestion.quiz_id.in_(quiz_ids))
        .group_by(QuizQuestion.quiz_id)
    )
    return {quiz_id: (n, float(total or 0)) for quiz_id, n, total in db.execute(query)}


def delete_questions(db: Session, quiz_id: str) -> None:
    """Questions of a draft quiz are replaced as a whole; once published they are frozen and never deleted."""
    for row in questions(db, quiz_id):
        db.delete(row)
    db.flush()


# ---------------------------------------------------------------- submissions and attempts


def submissions(db: Session, assignment_ids: list[str], **filters) -> list[Submission]:
    if not assignment_ids:
        return []
    query = q(db, Submission).where(Submission.assignment_id.in_(assignment_ids))
    if filters.get("student_id"):
        query = query.where(_is(Submission.student_id, filters["student_id"]))
    if filters.get("status"):
        query = query.where(Submission.status == filters["status"])
    if not filters.get("include_superseded"):
        query = query.where(Submission.status != "superseded")
    return list(db.scalars(query.order_by(Submission.submitted_at, Submission.id)))


def student_submissions(db: Session, student_id: str | Collection[str]) -> list[Submission]:
    query = q(db, Submission).where(_is(Submission.student_id, student_id))
    return list(db.scalars(query.order_by(Submission.submitted_at, Submission.attempt, Submission.id)))


def attempts(db: Session, quiz_ids: list[str], **filters) -> list[QuizAttempt]:
    if not quiz_ids:
        return []
    query = q(db, QuizAttempt).where(QuizAttempt.quiz_id.in_(quiz_ids))
    if filters.get("student_id"):
        query = query.where(_is(QuizAttempt.student_id, filters["student_id"]))
    if filters.get("manual_grading_state"):
        query = query.where(QuizAttempt.manual_grading_state == filters["manual_grading_state"])
    if filters.get("status"):
        query = query.where(QuizAttempt.status == filters["status"])
    return list(db.scalars(query.order_by(QuizAttempt.started_at, QuizAttempt.attempt_number, QuizAttempt.id)))


def student_attempts(db: Session, student_id: str | Collection[str]) -> list[QuizAttempt]:
    query = q(db, QuizAttempt).where(_is(QuizAttempt.student_id, student_id))
    return list(db.scalars(query.order_by(QuizAttempt.started_at, QuizAttempt.attempt_number, QuizAttempt.id)))


def overdue_attempts(db: Session, now) -> list[QuizAttempt]:
    """In-progress attempts past their deadline, in the session's organisation (or every organisation in platform
    scope, for the job)."""
    query = q(db, QuizAttempt).where(QuizAttempt.status == "in_progress", QuizAttempt.must_submit_by <= now)
    return list(db.scalars(query.order_by(QuizAttempt.must_submit_by, QuizAttempt.id)))


# ---------------------------------------------------------------- grades


def grades(db: Session, **filters) -> list[Grade]:
    query = q(db, Grade)
    for column in ("item_type", "item_id", "student_id", "course_space_id", "status"):
        if filters.get(column):
            query = query.where(_is(getattr(Grade, column), filters[column]))
    if filters.get("item_ids") is not None:
        query = query.where(Grade.item_id.in_(filters["item_ids"] or [""]))
    return list(db.scalars(query.order_by(Grade.created_at, Grade.id)))


def grade_for(db: Session, item_type: str, item_id: str, student_id: str) -> Grade | None:
    query = q(db, Grade).where(Grade.item_type == item_type, Grade.item_id == item_id, Grade.student_id == student_id)
    return db.scalars(query.with_for_update()).first()


# ---------------------------------------------------------------- discussions


def threads(db: Session, space_ids: list[str], include_hidden: bool) -> Select:
    query = q(db, DiscussionThread).where(DiscussionThread.course_space_id.in_(space_ids or [""]))
    if not include_hidden:
        query = query.where(DiscussionThread.hidden.is_(False))
    return query.order_by(DiscussionThread.last_activity_at.desc(), DiscussionThread.id)


def posts(db: Session, thread_id: str, include_hidden: bool) -> Select:
    query = q(db, DiscussionPost).where(DiscussionPost.thread_id == thread_id)
    if not include_hidden:
        query = query.where(DiscussionPost.state == "visible")
    return query.order_by(DiscussionPost.created_at, DiscussionPost.id)


def post_counts(db: Session, thread_ids: list[str]) -> dict[str, int]:
    """Visible posts per thread."""
    if not thread_ids:
        return {}
    query = (
        scoped(db, select(DiscussionPost.thread_id, func.count()), DiscussionPost)
        .where(DiscussionPost.thread_id.in_(thread_ids), DiscussionPost.state == "visible")
        .group_by(DiscussionPost.thread_id)
    )
    return dict(db.execute(query).all())


def all_posts(db: Session, thread_ids: list[str]) -> list[DiscussionPost]:
    if not thread_ids:
        return []
    return list(db.scalars(q(db, DiscussionPost).where(DiscussionPost.thread_id.in_(thread_ids))))


def all_threads(db: Session, space_ids: list[str]) -> list[DiscussionThread]:
    if not space_ids:
        return []
    return list(db.scalars(q(db, DiscussionThread).where(DiscussionThread.course_space_id.in_(space_ids))))
