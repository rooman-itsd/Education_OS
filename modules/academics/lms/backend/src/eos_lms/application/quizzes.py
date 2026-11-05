"""Quizzes, quiz attempts and essay scoring (FR-8 to FR-10). Each change checks the domain rules, writes an audit entry
and publishes its event to the outbox in the same transaction. Students never receive an answer key, and see their
scores only once the quiz grade is released."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import CourseSpace, Quiz, QuizAttempt, QuizQuestion, as_utc, iso
from . import access as k
from . import common as c
from . import scoring
from .access import Actor
from .coursework import published_units, unit_in, visible_to
from .errors import conflict, forbidden, invalid, not_found, unprocessable

# ---------------------------------------------------------------- serialisation


def quiz_dict(quiz: Quiz, stats: tuple[int, float], questions: list[QuizQuestion] | None = None) -> dict:
    out = {
        "id": quiz.id,
        "organisation_id": quiz.organisation_id,
        "course_space_id": quiz.course_space_id,
        "title": quiz.title,
        "unit_id": quiz.unit_id,
        "opens_at": iso(quiz.opens_at),
        "closes_at": iso(quiz.closes_at),
        "time_limit_minutes": quiz.time_limit_minutes,
        "attempts_allowed": quiz.attempts_allowed,
        "attempt_scoring": quiz.attempt_scoring,
        "auto_release": quiz.auto_release,
        "status": quiz.status,
        "question_count": stats[0],
        "max_points": stats[1],
        "published_at": iso(quiz.published_at),
    }
    if questions is not None:
        out["questions"] = [_question_out(q, with_key=True) for q in questions]
    return out


def _question_out(q: QuizQuestion, with_key: bool) -> dict:
    out = {"id": q.id, "position": q.position, "question_type": q.question_type, "prompt": q.prompt, "points": q.points}
    if q.options is not None:
        out["options"] = list(q.options)
    if with_key and q.answer_key is not None:
        out["answer_key"] = q.answer_key
    return out


def attempt_dict(t: QuizAttempt, show_scores: bool = True) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "quiz_id": t.quiz_id,
        "student_id": t.student_id,
        "attempt_number": t.attempt_number,
        "started_at": iso(t.started_at),
        "must_submit_by": iso(t.must_submit_by),
        "submitted_at": iso(t.submitted_at),
        "submitted_by_system": t.submitted_by_system,
        "answers": list(t.answers or []),
        "auto_score": t.auto_score if show_scores else None,
        "manual_score": t.manual_score if show_scores else None,
        "manual_grading_state": t.manual_grading_state,
        "status": t.status,
    }


def _released_quizzes(db: Session, student_id: str) -> set[str]:
    return {g.item_id for g in repo.grades(db, item_type="quiz", student_id=student_id, status="released")}


def _stats(db: Session, quiz: Quiz) -> tuple[int, float]:
    return repo.question_stats(db, [quiz.id]).get(quiz.id, (0, 0.0))


# ---------------------------------------------------------------- quizzes


def _store_questions(db: Session, a: Actor, quiz: Quiz, questions: list[dict]) -> None:
    for q in questions:
        c.check(rules.check_question, q)
    for i, q in enumerate(questions):
        db.add(
            QuizQuestion(
                organisation_id=a.organisation_id,
                quiz_id=quiz.id,
                position=i,
                question_type=q["question_type"],
                prompt=q["prompt"],
                options=q.get("options"),
                answer_key=q.get("answer_key"),
                points=q["points"],
            )
        )
    db.flush()


def list_quizzes(db: Session, a: Actor, space_id: str, status: str | None, unit_id: str | None) -> dict:
    space = c.space_of(db, space_id)
    view = c.viewer(db, a, space)
    units = published_units(db, space.id)
    rows = [
        x
        for x in repo.quizzes(db, [space.id])
        if visible_to(view, x, units)
        and (status is None or x.status == status)
        and (unit_id is None or x.unit_id == unit_id)
    ]
    stats = repo.question_stats(db, [x.id for x in rows])
    return {"items": [quiz_dict(x, stats.get(x.id, (0, 0.0))) for x in rows]}


def create_quiz(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.QUIZ_MANAGE_ASSIGNED)
    c.require_writable(space)
    c.check(rules.check_quiz_window, body["opens_at"], body["closes_at"])
    unit_in(db, space, body.get("unit_id"))
    quiz = Quiz(
        organisation_id=a.organisation_id,
        course_space_id=space.id,
        unit_id=body.get("unit_id"),
        title=body["title"],
        opens_at=body["opens_at"],
        closes_at=body["closes_at"],
        time_limit_minutes=body.get("time_limit_minutes"),
        attempts_allowed=body.get("attempts_allowed", 1),
        attempt_scoring=body.get("attempt_scoring", "highest"),
        auto_release=body.get("auto_release", False),
        status="draft",
        created_by=a.user_id,
        created_at=c.clock(),
    )
    db.add(quiz)
    db.flush()
    _store_questions(db, a, quiz, body["questions"])
    c.audit(db, a, "quiz.created", "quiz", quiz.id, a.organisation_id)
    db.commit()
    return quiz_dict(quiz, _stats(db, quiz), repo.questions(db, quiz.id))


def get_quiz(db: Session, a: Actor, quiz_id: str) -> dict:
    quiz = c.get(db, Quiz, quiz_id, "quiz")
    space = c.space_of(db, quiz.course_space_id)
    view = c.viewer(db, a, space)
    if not visible_to(view, quiz, published_units(db, space.id)):
        raise not_found("quiz")
    managing = c.staff_of(db, a, space, k.QUIZ_MANAGE_ASSIGNED)
    return quiz_dict(quiz, _stats(db, quiz), repo.questions(db, quiz.id) if managing else None)


def update_quiz(db: Session, a: Actor, quiz_id: str, body: dict) -> dict:
    quiz = c.get(db, Quiz, quiz_id, "quiz", for_update=True)
    space = c.space_of(db, quiz.course_space_id)
    c.require_scope(db, a, space, k.QUIZ_MANAGE_ASSIGNED)
    c.require_writable(space)
    if quiz.status == "closed":
        raise conflict("invalid_status", "a closed quiz cannot be edited")
    if body.get("questions") is not None and quiz.status != "draft":
        raise conflict("questions_frozen", "questions cannot change once the quiz is published")
    if "unit_id" in body:
        unit_in(db, space, body["unit_id"])
    for name in ("title", "opens_at", "closes_at", "attempts_allowed", "attempt_scoring", "auto_release"):
        if body.get(name) is not None:
            setattr(quiz, name, body[name])
    for name in ("unit_id", "time_limit_minutes"):
        if name in body:
            setattr(quiz, name, body[name])
    c.check(rules.check_quiz_window, as_utc(quiz.opens_at), as_utc(quiz.closes_at))
    if body.get("questions") is not None:
        repo.delete_questions(db, quiz.id)
        _store_questions(db, a, quiz, body["questions"])
    c.audit(db, a, "quiz.updated", "quiz", quiz.id, a.organisation_id)
    db.commit()
    return quiz_dict(quiz, _stats(db, quiz), repo.questions(db, quiz.id))


def change_quiz_status(db: Session, a: Actor, quiz_id: str, status: str) -> dict:
    quiz = c.get(db, Quiz, quiz_id, "quiz", for_update=True)
    space = c.space_of(db, quiz.course_space_id)
    c.require_scope(db, a, space, k.QUIZ_MANAGE_ASSIGNED)
    c.require_writable(space)
    quiz.status = c.check(rules.transition, rules.WORK_TRANSITIONS, status, quiz.status, "quiz")
    c.audit(db, a, f"quiz.{status}", "quiz", quiz.id, a.organisation_id)
    if status == "published":
        quiz.published_at = c.clock()
        c.publish(
            db,
            a,
            "quiz.published",
            a.organisation_id,
            {
                "quiz_id": quiz.id,
                "course_space_id": space.id,
                "course_offering_id": space.course_offering_id,
                "title": quiz.title,
                "opens_at": iso(quiz.opens_at),
                "closes_at": iso(quiz.closes_at),
                "time_limit_minutes": quiz.time_limit_minutes,
                "attempts_allowed": quiz.attempts_allowed,
                "published_at": iso(quiz.published_at),
            },
        )
    db.commit()
    return quiz_dict(quiz, _stats(db, quiz), repo.questions(db, quiz.id))


# ---------------------------------------------------------------- attempts


def start_attempt(db: Session, a: Actor, quiz_id: str) -> dict:
    quiz = c.get(db, Quiz, quiz_id, "quiz", for_update=True)
    space = c.space_of(db, quiz.course_space_id)
    view = c.viewer(db, a, space)
    if not view.learner:
        raise forbidden("only students of the course space attempt quizzes", "not_a_student")
    if not visible_to(view, quiz, published_units(db, space.id)):
        raise not_found("quiz")
    mine = repo.attempts(db, [quiz.id], student_id=a.user_id)
    if scoring.settle(db, mine):
        db.commit()  # what settling submitted stands, whatever this request decides
    now = c.clock()
    if quiz.status != "published" or space.status != "active":
        raise conflict("quiz_not_open", "the quiz is not open")
    if not as_utc(quiz.opens_at) <= now < as_utc(quiz.closes_at):
        raise conflict("quiz_not_open", "the quiz is not open now")
    if any(t.status == "in_progress" for t in mine):
        raise conflict("attempt_in_progress", "an attempt is already in progress")
    if len(mine) >= quiz.attempts_allowed:
        raise conflict("no_attempts_left", f"all {quiz.attempts_allowed} attempts have been used")
    t = QuizAttempt(
        organisation_id=a.organisation_id,
        quiz_id=quiz.id,
        course_space_id=space.id,
        student_id=a.user_id,
        attempt_number=len(mine) + 1,
        started_at=now,
        must_submit_by=rules.must_submit_by(now, quiz.time_limit_minutes, as_utc(quiz.closes_at)),
        submitted_by_system=False,
        answers=[],
        question_scores={},
        manual_grading_state="none",
        status="in_progress",
    )
    db.add(t)
    c.flush_unique(db, "attempt_in_progress", "another attempt was started at the same moment")
    c.audit(db, a, "quiz-attempt.started", "quiz-attempt", t.id, a.organisation_id)
    db.commit()
    out = attempt_dict(t, show_scores=False)
    out["questions"] = [_question_out(q, with_key=False) for q in repo.questions(db, quiz.id)]
    return out


def _own_attempt(db: Session, a: Actor, attempt_id: str) -> tuple[QuizAttempt, Quiz]:
    t = c.get(db, QuizAttempt, attempt_id, "quiz attempt", for_update=True)
    if t.student_id != a.user_id:
        raise not_found("quiz attempt")
    return t, c.get(db, Quiz, t.quiz_id, "quiz")


def save_answers(db: Session, a: Actor, attempt_id: str, answers: list[dict]) -> dict:
    t, quiz = _own_attempt(db, a, attempt_id)
    if scoring.settle(db, [t]):
        db.commit()
    if t.status != "in_progress":
        raise conflict("attempt_not_in_progress", "the attempt is no longer in progress")
    questions = {q.id: scoring.question_dict(q) for q in repo.questions(db, quiz.id)}
    seen: set[str] = set()
    for answer in answers:
        qid = answer["question_id"]
        if qid not in questions:
            raise invalid("invalid_answer", "an answer names a question that is not in this quiz", question_id=qid)
        if qid in seen:
            raise invalid("invalid_answer", "a question is answered twice", question_id=qid)
        seen.add(qid)
        c.check(rules.check_answer, questions[qid], answer)
    merged = {x["question_id"]: x for x in (t.answers or [])}
    for answer in answers:
        merged[answer["question_id"]] = {key: v for key, v in answer.items() if v is not None}
    t.answers = list(merged.values())
    c.audit(db, a, "quiz-attempt.answered", "quiz-attempt", t.id, a.organisation_id)
    db.commit()
    return attempt_dict(t, show_scores=False)


def submit_attempt(db: Session, a: Actor, attempt_id: str) -> dict:
    t, quiz = _own_attempt(db, a, attempt_id)
    if scoring.settle(db, [t]):
        db.commit()
    if t.status != "in_progress":
        raise conflict("attempt_not_in_progress", "the attempt is no longer in progress")
    space = c.space_of(db, quiz.course_space_id)
    scoring.finish(db, a, t, quiz, space, c.clock(), by_system=False)
    db.commit()
    return attempt_dict(t, show_scores=quiz.id in _released_quizzes(db, a.user_id))


def score_attempt(db: Session, a: Actor, attempt_id: str, scores: list[dict]) -> dict:
    t = c.get(db, QuizAttempt, attempt_id, "quiz attempt", for_update=True)
    quiz = c.get(db, Quiz, t.quiz_id, "quiz")
    space = c.space_of(db, quiz.course_space_id)
    c.require_scope(db, a, space, k.GRADE_MANAGE_ASSIGNED)
    c.require_writable(space)
    if scoring.settle(db, [t]):
        db.commit()
    if t.status == "in_progress":
        raise unprocessable("attempt_not_submitted", "the attempt has not been submitted yet")
    essays = {q.id: q for q in repo.questions(db, quiz.id) if q.question_type == "essay"}
    if len({s["question_id"] for s in scores}) != len(scores):
        raise invalid("invalid_request", "a question is scored twice")
    question_scores = dict(t.question_scores or {})
    for s in scores:
        q = essays.get(s["question_id"])
        if q is None:
            raise unprocessable("not_an_essay", "only essay questions of this quiz are scored by hand")
        c.check(rules.check_points, s["points"], q.points)
        question_scores[q.id] = {"points": s["points"], "comment": s.get("comment")}
    t.question_scores = question_scores
    t.manual_score = round(sum(v["points"] for qid, v in question_scores.items() if qid in essays), 4)
    if all(qid in question_scores for qid in essays):
        t.manual_grading_state, t.status = "done", "graded"
    c.audit(db, a, "quiz-attempt.scored", "quiz-attempt", t.id, a.organisation_id)
    db.flush()
    if t.status == "graded":
        scoring.sync_quiz_grade(db, a, quiz, space, t.student_id)
    db.commit()
    return attempt_dict(t)


def list_attempts(db: Session, a: Actor, quiz_id: str, state: str | None, limit: int, offset: int) -> dict:
    quiz = c.get(db, Quiz, quiz_id, "quiz")
    space = c.space_of(db, quiz.course_space_id)
    c.require_scope(db, a, space, k.QUIZ_ATTEMPT_READ_ASSIGNED)
    scoring.settle_quizzes(db, [quiz.id])
    rows = repo.attempts(db, [quiz.id], manual_grading_state=state)
    return {"items": [attempt_dict(t) for t in rows[offset : offset + limit]], "total": len(rows)}


def my_attempts(db: Session, a: Actor, quiz_id: str | None, space_id: str | None) -> dict:
    rows = repo.student_attempts(db, a.user_id)
    if scoring.settle(db, rows):
        db.commit()
    if quiz_id:
        rows = [t for t in rows if t.quiz_id == quiz_id]
    if space_id:
        rows = [t for t in rows if t.course_space_id == space_id]
    released = _released_quizzes(db, a.user_id)
    return {"items": [attempt_dict(t, show_scores=t.quiz_id in released) for t in rows]}
