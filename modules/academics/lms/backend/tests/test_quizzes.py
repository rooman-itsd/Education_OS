"""Quizzes, attempts, automatic and essay scoring, the time limit and the grade they produce (FR-8 to FR-12)."""

from datetime import timedelta

from conftest import NOW, Course, Org, at, audit_actions, outbox, set_clock
from eos_core.db import SessionLocal
from eos_lms.application import jobs
from eos_lms.infrastructure.models import new_id

ESSAY_QUIZ = [
    {"question_type": "single_choice", "prompt": "2+2?", "options": ["3", "4"], "answer_key": [1], "points": 2},
    {"question_type": "essay", "prompt": "Explain", "points": 3},
]


def answers_for(attempt: dict, *values) -> list[dict]:
    return [{"question_id": q["id"], **v} for q, v in zip(attempt["questions"], values, strict=True)]


def test_quiz_questions_are_validated(course):
    c = course
    base = f"/course-spaces/{c.space['id']}/quizzes"
    good = {"title": "Q", "opens_at": at(), "closes_at": at(days=1)}
    bad_questions = [
        {"question_type": "single_choice", "prompt": "x", "options": ["a"], "answer_key": [0], "points": 1},
        {"question_type": "single_choice", "prompt": "x", "options": ["a", "b"], "answer_key": [0, 1], "points": 1},
        {"question_type": "multiple_choice", "prompt": "x", "options": ["a", "b"], "answer_key": [2], "points": 1},
        {"question_type": "multiple_choice", "prompt": "x", "options": ["a", "b"], "answer_key": [True], "points": 1},
        {"question_type": "multiple_choice", "prompt": "x", "options": ["a", "b"], "answer_key": ["0"], "points": 1},
        {"question_type": "true_false", "prompt": "x", "answer_key": "true", "points": 1},
        {"question_type": "true_false", "prompt": "x", "answer_key": True, "options": ["a", "b"], "points": 1},
        {"question_type": "short_answer", "prompt": "x", "answer_key": [], "points": 1},
        {"question_type": "essay", "prompt": "x", "answer_key": ["no"], "points": 1},
        {"question_type": "essay", "prompt": "x", "points": 0},
        {"question_type": "essay", "prompt": "", "points": 1},
    ]
    for q in bad_questions:
        r = c.call("POST", base, {**good, "questions": [q]}, c.teacher)
        assert r.status_code == 400, (q, r.text)
    assert c.call("POST", base, {**good, "questions": []}, c.teacher).status_code == 400
    window = {**good, "closes_at": at(), "questions": ESSAY_QUIZ}
    r = c.call("POST", base, window, c.teacher)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_window"
    for field, value in (("time_limit_minutes", 0), ("time_limit_minutes", 10_081), ("attempts_allowed", 101)):
        assert c.call("POST", base, {**good, field: value, "questions": ESSAY_QUIZ}, c.teacher).status_code == 400
    created = c.post(base, {**good, "questions": ESSAY_QUIZ}, 201, c.teacher)
    assert created["question_count"] == 2 and created["max_points"] == 5
    assert created["attempt_scoring"] == "highest" and created["auto_release"] is False


def test_quiz_editing_freezes_questions_once_published(course):
    c = course
    qz = c.quiz(publish=False)
    edited = c.patch(f"/quizzes/{qz['id']}", {"questions": ESSAY_QUIZ, "title": "Renamed"}, c.teacher)
    assert edited["title"] == "Renamed" and [q["question_type"] for q in edited["questions"]] == [
        "single_choice",
        "essay",
    ]
    published = c.post(f"/quizzes/{qz['id']}/status", {"status": "published"}, headers=c.teacher)
    assert outbox("lms.quiz.published", c.org.id) == [
        {
            "organisation_id": c.org.id,
            "quiz_id": qz["id"],
            "course_space_id": c.space["id"],
            "course_offering_id": c.offering,
            "title": "Renamed",
            "opens_at": at(hours=-1),
            "closes_at": at(days=2),
            "time_limit_minutes": None,
            "attempts_allowed": 2,
            "published_at": published["published_at"],
        }
    ]
    r = c.call("PATCH", f"/quizzes/{qz['id']}", {"questions": ESSAY_QUIZ}, c.teacher)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "questions_frozen"
    assert (
        c.patch(f"/quizzes/{qz['id']}", {"closes_at": at(days=3), "attempts_allowed": 3}, c.teacher)["attempts_allowed"]
        == 3
    )
    r = c.call("PATCH", f"/quizzes/{qz['id']}", {"closes_at": at(hours=-2)}, c.teacher)
    assert r.status_code == 400
    c.post(f"/quizzes/{qz['id']}/status", {"status": "closed"}, headers=c.teacher)
    assert c.call("PATCH", f"/quizzes/{qz['id']}", {"title": "x"}, c.teacher).status_code == 409


def test_students_get_settings_but_never_questions_or_keys(course):
    c = course
    qz = c.quiz()
    seen = c.get(f"/quizzes/{qz['id']}", c.student)
    assert "questions" not in seen and seen["question_count"] == 2
    assert all("answer_key" in q for q in c.get(f"/quizzes/{qz['id']}", c.teacher)["questions"])
    assert "questions" not in c.get(f"/quizzes/{qz['id']}", c.viewer)
    draft = c.quiz(publish=False)
    assert c.call("GET", f"/quizzes/{draft['id']}", headers=c.student).status_code == 404
    assert [x["id"] for x in c.get(f"/course-spaces/{c.space['id']}/quizzes", c.student)["items"]] == [qz["id"]]
    assert len(c.get(f"/course-spaces/{c.space['id']}/quizzes?status=draft", c.teacher)["items"]) == 1


def test_automatic_scoring_and_auto_release(course):
    c = course
    qz = c.quiz(auto_release=True)
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    assert attempt["attempt_number"] == 1 and attempt["status"] == "in_progress"
    assert attempt["must_submit_by"] == at(days=2) and all("answer_key" not in q for q in attempt["questions"])
    saved = c.put(
        f"/attempts/{attempt['id']}/answers",
        {"answers": answers_for(attempt, {"selected_options": [1]}, {"boolean_answer": False})},
        c.student,
    )
    assert len(saved["answers"]) == 2 and saved["auto_score"] is None
    # Answers can be changed while in progress.
    c.put(
        f"/attempts/{attempt['id']}/answers",
        {"answers": answers_for(attempt, {"selected_options": [1]}, {"boolean_answer": True})},
        c.student,
    )
    done = c.post(f"/attempts/{attempt['id']}/submit", None, headers=c.student)
    assert done["status"] == "graded" and done["manual_grading_state"] == "none"
    assert done["auto_score"] == 3  # released at once, so the student sees it
    assert outbox("lms.quiz-attempt.submitted", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "attempt_id": attempt["id"],
        "quiz_id": qz["id"],
        "course_space_id": c.space["id"],
        "student_id": c.student_id,
        "attempt_number": 1,
        "submitted_at": NOW.isoformat(),
        "submitted_by_system": False,
        "auto_score": 3.0,
        "needs_manual_grading": False,
    }
    released = outbox("lms.grade.released", c.org.id)
    assert [(g["item_type"], g["points"], g["max_points"], g["version"]) for g in released] == [("quiz", 3.0, 3.0, 1)]
    grades = c.get("/me/grades", c.student)["items"]
    assert grades[0]["released_points"] == 3 and grades[0]["course_title"] == "Programming"
    r = c.call("POST", f"/attempts/{attempt['id']}/submit", None, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "attempt_not_in_progress"


def test_scores_stay_hidden_until_the_grade_is_released(course):
    c = course
    qz = c.quiz()
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    done = c.post(f"/attempts/{attempt['id']}/submit", None, headers=c.student)
    assert done["auto_score"] is None and done["status"] == "graded"
    assert c.get("/me/quiz-attempts", c.student)["items"][0]["auto_score"] is None
    assert c.get(f"/quizzes/{qz['id']}/attempts", c.teacher)["items"][0]["auto_score"] == 0
    c.post("/grades/release", {"item_type": "quiz", "item_id": qz["id"]}, headers=c.teacher)
    assert c.get(f"/me/quiz-attempts?quiz_id={qz['id']}", c.student)["items"][0]["auto_score"] == 0


def test_essays_wait_for_the_instructor(course):
    c = course
    qz = c.quiz(questions=ESSAY_QUIZ, auto_release=True)
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    c.put(
        f"/attempts/{attempt['id']}/answers",
        {"answers": answers_for(attempt, {"selected_options": [1]}, {"text_answer": "Because"})},
        c.student,
    )
    done = c.post(f"/attempts/{attempt['id']}/submit", None, headers=c.student)
    assert (done["status"], done["manual_grading_state"]) == ("submitted", "pending")
    assert outbox("lms.quiz-attempt.submitted", c.org.id)[-1]["needs_manual_grading"] is True
    assert c.get(f"/quizzes/{qz['id']}/attempts?manual_grading_state=pending", c.teacher)["total"] == 1
    essay, choice = attempt["questions"][1]["id"], attempt["questions"][0]["id"]
    path = f"/attempts/{attempt['id']}/scores"
    for bad, status in (
        ({"scores": [{"question_id": essay, "points": 4}]}, 422),
        ({"scores": [{"question_id": choice, "points": 1}]}, 422),
        ({"scores": [{"question_id": new_id(), "points": 1}]}, 422),
        ({"scores": [{"question_id": essay, "points": -1}]}, 400),
        ({"scores": []}, 400),
    ):
        assert c.call("PATCH", path, bad, c.teacher).status_code == status, bad
    assert c.call("PATCH", path, {"scores": [{"question_id": essay, "points": 2}]}, c.student).status_code == 403
    scored = c.patch(path, {"scores": [{"question_id": essay, "points": 2.5, "comment": "Fair"}]}, c.teacher)
    assert (scored["status"], scored["manual_grading_state"], scored["manual_score"]) == ("graded", "done", 2.5)
    grade = c.get("/me/grades", c.student)["items"][0]["grades"][0]
    assert (grade["points"], grade["max_points"], grade["status"]) == (4.5, 5, "released")
    assert "quiz-attempt.scored" in audit_actions(c.org.id, attempt["id"])


def test_attempt_rules(course, monkeypatch, org):
    c = course
    qz = c.quiz(attempts_allowed=1, time_limit_minutes=30)
    path = f"/quizzes/{qz['id']}/attempts"
    attempt = c.post(path, None, 201, c.student)
    assert attempt["must_submit_by"] == at(hours=0.5)
    r = c.call("POST", path, None, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "attempt_in_progress"
    assert c.call("POST", path, None, c.teacher).status_code == 403
    # Another student cannot touch this attempt.
    other = c.call("PUT", f"/attempts/{attempt['id']}/answers", {"answers": []}, c.student2)
    assert other.status_code == 404
    bad = [{"question_id": attempt["questions"][0]["id"], "boolean_answer": True}]
    assert c.call("PUT", f"/attempts/{attempt['id']}/answers", {"answers": bad}, c.student).status_code == 400
    twice = [{"question_id": attempt["questions"][1]["id"], "boolean_answer": True}] * 2
    assert c.call("PUT", f"/attempts/{attempt['id']}/answers", {"answers": twice}, c.student).status_code == 400
    wrong_option = [{"question_id": attempt["questions"][0]["id"], "selected_options": [5]}]
    assert c.call("PUT", f"/attempts/{attempt['id']}/answers", {"answers": wrong_option}, c.student).status_code == 400
    # Past the time limit the system submits it, and the student can no longer answer.
    set_clock(monkeypatch, NOW + timedelta(minutes=31))
    r = c.call("PUT", f"/attempts/{attempt['id']}/answers", {"answers": []}, c.student)
    assert r.status_code == 409
    mine = c.get("/me/quiz-attempts", c.student)["items"][0]
    assert mine["submitted_by_system"] is True and mine["submitted_at"] == at(hours=0.5)
    r = c.call("POST", path, None, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_attempts_left"


def test_quiz_window(course, monkeypatch):
    c = course
    later = c.quiz(opens_at=at(days=1), closes_at=at(days=2))
    r = c.call("POST", f"/quizzes/{later['id']}/attempts", None, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "quiz_not_open"
    set_clock(monkeypatch, NOW + timedelta(days=3))
    assert c.call("POST", f"/quizzes/{later['id']}/attempts", None, c.student).status_code == 409


def test_highest_and_latest_attempt_scoring(course, monkeypatch):
    c = course
    for scoring, expected in (("highest", 3), ("latest", 0)):
        qz = c.quiz(attempt_scoring=scoring)
        first = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
        c.put(
            f"/attempts/{first['id']}/answers",
            {"answers": answers_for(first, {"selected_options": [1]}, {"boolean_answer": True})},
            c.student,
        )
        c.post(f"/attempts/{first['id']}/submit", None, headers=c.student)
        second = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
        c.post(f"/attempts/{second['id']}/submit", None, headers=c.student)
        book = c.get(f"/course-spaces/{c.space['id']}/gradebook", c.teacher)
        cell = next(
            cell
            for s in book["students"]
            if s["student_id"] == c.student_id
            for cell in s["cells"]
            if cell["item_id"] == qz["id"]
        )
        assert (cell["status"], cell["points"]) == ("graded", expected), scoring


def test_the_job_submits_overdue_attempts_across_organisations(client, course, monkeypatch):
    c = course
    qz = c.quiz(time_limit_minutes=10)
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    other = Course(client, Org())
    oq = other.quiz(time_limit_minutes=10)
    other.post(f"/quizzes/{oq['id']}/attempts", None, 201, other.student)
    with SessionLocal() as db:
        jobs.submit_overdue_attempts(db)
    assert outbox("lms.quiz-attempt.submitted", c.org.id) == []  # not due yet
    set_clock(monkeypatch, NOW + timedelta(minutes=11))
    with SessionLocal() as db:
        assert jobs.submit_overdue_attempts(db) >= 2
    events = outbox("lms.quiz-attempt.submitted", c.org.id)
    assert [e["attempt_id"] for e in events] == [attempt["id"]] and events[0]["submitted_by_system"] is True
    assert outbox("lms.quiz-attempt.submitted", other.org.id)[0]["organisation_id"] == other.org.id
