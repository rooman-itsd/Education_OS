"""Finishing quiz attempts and keeping coursework grades in step with them (FR-9 to FR-12), shared by the quiz, grade
and job use cases.

An attempt still running at its deadline (the earlier of its time limit and the quiz's closing time) is submitted by
the system, at that deadline, the next time anything looks at it: a student saving or submitting, an instructor
listing attempts, the grading queue, or the job in application/jobs.py."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import CourseSpace, Grade, Quiz, QuizAttempt, QuizQuestion, as_utc, iso
from . import common as c
from .access import Actor


def question_dict(q: QuizQuestion) -> dict:
    return {
        "id": q.id,
        "question_type": q.question_type,
        "prompt": q.prompt,
        "options": q.options,
        "answer_key": q.answer_key,
        "points": q.points,
    }


def quiz_max_points(db: Session, quiz_id: str) -> float:
    return repo.question_stats(db, [quiz_id]).get(quiz_id, (0, 0.0))[1]


def release(db: Session, actor: Actor | None, g: Grade, space: CourseSpace) -> None:
    """Release a grade to its student and publish lms.grade.released."""
    g.status = "released"
    g.released_at = c.clock()
    c.audit(db, actor, "grade.released", "grade", g.id, g.organisation_id)
    c.publish(
        db,
        actor,
        "grade.released",
        g.organisation_id,
        {
            "grade_id": g.id,
            "course_space_id": space.id,
            "course_offering_id": space.course_offering_id,
            "item_type": g.item_type,
            "item_id": g.item_id,
            "student_id": g.student_id,
            "points": g.points,
            "max_points": g.max_points,
            "version": g.version,
            "released_at": iso(g.released_at),
        },
    )


def sync_quiz_grade(db: Session, actor: Actor | None, quiz: Quiz, space: CourseSpace, student_id: str) -> None:
    """The student's quiz grade from their attempts by the quiz's attempt_scoring. A grade an instructor entered by hand
    is left alone. A released grade whose points change gets a new version and is released again."""
    attempts = [
        {"attempt_number": t.attempt_number, "status": t.status, "total": (t.auto_score or 0) + (t.manual_score or 0)}
        for t in repo.attempts(db, [quiz.id], student_id=student_id)
    ]
    chosen = rules.attempt_for_grade(attempts, quiz.attempt_scoring)
    if chosen is None:
        return
    points, max_points = round(chosen["total"], 4), quiz_max_points(db, quiz.id)
    g = repo.grade_for(db, "quiz", quiz.id, student_id)
    if g is None:
        g = Grade(
            organisation_id=quiz.organisation_id,
            item_type="quiz",
            item_id=quiz.id,
            course_space_id=space.id,
            student_id=student_id,
            points=points,
            max_points=max_points,
            status="draft",
            version=1,
            source="attempts",
            created_at=c.clock(),
        )
        db.add(g)
        db.flush()
        c.audit(db, actor, "grade.created", "grade", g.id, g.organisation_id)
    elif g.source == "manual" or g.points == points:
        pass
    elif g.status == "released":
        g.points, g.max_points, g.version = points, max_points, g.version + 1
        g.change_reason = "recomputed from the quiz attempts"
        c.audit(db, actor, "grade.changed", "grade", g.id, g.organisation_id)
        release(db, actor, g, space)
        return
    else:
        g.points, g.max_points = points, max_points
        c.audit(db, actor, "grade.updated", "grade", g.id, g.organisation_id)
    if quiz.auto_release and g.status == "draft":
        release(db, actor, g, space)


def finish(
    db: Session, actor: Actor | None, t: QuizAttempt, quiz: Quiz, space: CourseSpace, at: datetime, by_system: bool
) -> None:
    """Submit the attempt: score its automatic questions, wait for an instructor when it has essays, otherwise grade
    it. Publishes lms.quiz-attempt.submitted."""
    questions = [question_dict(q) for q in repo.questions(db, quiz.id)]
    auto, needs_manual = rules.score_attempt(questions, list(t.answers or []))
    t.auto_score = round(auto, 4)
    t.submitted_at = at
    t.submitted_by_system = by_system
    t.manual_grading_state = "pending" if needs_manual else "none"
    t.status = "submitted" if needs_manual else "graded"
    c.audit(db, actor, "quiz-attempt.submitted", "quiz-attempt", t.id, t.organisation_id)
    c.publish(
        db,
        actor,
        "quiz-attempt.submitted",
        t.organisation_id,
        {
            "attempt_id": t.id,
            "quiz_id": quiz.id,
            "course_space_id": space.id,
            "student_id": t.student_id,
            "attempt_number": t.attempt_number,
            "submitted_at": iso(t.submitted_at),
            "submitted_by_system": by_system,
            "auto_score": t.auto_score,
            "needs_manual_grading": needs_manual,
        },
    )
    db.flush()
    if not needs_manual:
        sync_quiz_grade(db, actor, quiz, space, t.student_id)


def settle(db: Session, attempts: list[QuizAttempt]) -> bool:
    """Submit, as the system, every attempt in the list that is still running past its deadline. True if any was."""
    now, changed = c.clock(), False
    for t in attempts:
        if t.status == "in_progress" and as_utc(t.must_submit_by) <= now:
            quiz = repo.get(db, Quiz, t.quiz_id)
            space = repo.get(db, CourseSpace, t.course_space_id)
            finish(db, None, t, quiz, space, as_utc(t.must_submit_by), by_system=True)
            changed = True
    return changed


def settle_quizzes(db: Session, quiz_ids: list[str]) -> None:
    """Settle the running attempts of these quizzes and commit, so readers see the submitted state."""
    if settle(db, repo.attempts(db, quiz_ids, status="in_progress")):
        db.commit()
