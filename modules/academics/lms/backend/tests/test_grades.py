"""Coursework grades, feedback, release and the gradebook (FR-11 to FR-13). Coursework grades only."""

from conftest import FACULTY, HEAD, at, audit_actions, outbox
from eos_lms.infrastructure.models import new_id


def grades_body(item: dict, *entries: dict, item_type: str = "assignment") -> dict:
    return {"item_type": item_type, "item_id": item["id"], "entries": list(entries)}


def test_enter_release_and_change_a_grade(course):
    c = course
    x = c.assignment()
    sub = c.post(f"/assignments/{x['id']}/submissions", {"text": "mine"}, 201, c.student)
    entry = {"student_id": c.student_id, "points": 7.5, "feedback": "Good structure"}
    g = c.put("/grades", grades_body(x, entry), c.teacher)["items"][0]
    assert (g["status"], g["version"], g["points"], g["max_points"]) == ("draft", 1, 7.5, 10)
    assert c.get("/me/submissions", c.student)["items"][0]["status"] == "graded" and sub["status"] == "submitted"
    assert c.get("/me/grades", c.student)["items"] == []  # drafts are not shown to students
    # A draft may change freely.
    c.put("/grades", grades_body(x, {**entry, "points": 8}), c.teacher)
    summary = c.post("/grades/release", {"item_type": "assignment", "item_id": x["id"]}, headers=c.teacher)
    assert summary == {"released": 1, "skipped": 0}
    released = outbox("lms.grade.released", c.org.id)
    assert released == [
        {
            "organisation_id": c.org.id,
            "grade_id": g["id"],
            "course_space_id": c.space["id"],
            "course_offering_id": c.offering,
            "item_type": "assignment",
            "item_id": x["id"],
            "student_id": c.student_id,
            "points": 8.0,
            "max_points": 10.0,
            "version": 1,
            "released_at": released[0]["released_at"],
        }
    ]
    mine = c.get("/me/grades", c.student)["items"][0]
    assert (mine["released_points"], mine["released_max_points"]) == (8, 10)
    assert mine["grades"][0]["feedback"] == "Good structure"
    # Changing a released grade needs a reason, makes a new version and releases it again.
    r = c.call("PUT", "/grades", grades_body(x, {"student_id": c.student_id, "points": 9}), c.teacher)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "reason_required"
    changed = c.put(
        "/grades", grades_body(x, {"student_id": c.student_id, "points": 9, "reason": "Recount"}), c.teacher
    )
    g2 = changed["items"][0]
    assert (g2["version"], g2["status"], g2["change_reason"], g2["feedback"]) == (
        2,
        "released",
        "Recount",
        "Good structure",
    )
    assert [e["version"] for e in outbox("lms.grade.released", c.org.id)] == [1, 2]
    assert sorted(set(audit_actions(c.org.id, g["id"]))) == [
        "grade.changed",
        "grade.created",
        "grade.released",
        "grade.updated",
    ]


def test_grade_entry_rules(course, org):
    c = course
    x = c.assignment()
    over = c.call("PUT", "/grades", grades_body(x, {"student_id": c.student_id, "points": 11}), c.teacher)
    assert over.status_code == 422 and over.json()["detail"]["code"] == "points_out_of_range"
    stranger = c.call("PUT", "/grades", grades_body(x, {"student_id": new_id(), "points": 1}), c.teacher)
    assert stranger.status_code == 422 and stranger.json()["detail"]["code"] == "unknown_student"
    twice = grades_body(x, {"student_id": c.student_id, "points": 1}, {"student_id": c.student_id, "points": 2})
    assert c.call("PUT", "/grades", twice, c.teacher).status_code == 400
    draft = c.assignment(publish=False)
    r = c.call("PUT", "/grades", grades_body(draft, {"student_id": c.student_id, "points": 1}), c.teacher)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "item_not_published"
    _, other_teacher = org.user(FACULTY)
    r = c.call("PUT", "/grades", grades_body(x, {"student_id": c.student_id, "points": 1}), other_teacher)
    assert r.status_code == 403
    assert (
        c.call("PUT", "/grades", grades_body(x, {"student_id": c.student_id, "points": 1}), c.student).status_code
        == 403
    )
    assert (
        c.call("PUT", "/grades", {"item_type": "exam", "item_id": x["id"], "entries": []}, c.teacher).status_code == 400
    )
    # Overriding a quiz score needs a reason.
    qz = c.quiz()
    r = c.call(
        "PUT", "/grades", grades_body(qz, {"student_id": c.student_id, "points": 1}, item_type="quiz"), c.teacher
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "reason_required"
    ok = grades_body(qz, {"student_id": c.student_id, "points": 1, "reason": "Viva"}, item_type="quiz")
    assert c.put("/grades", ok, c.teacher)["items"][0]["max_points"] == 3


def test_release_for_listed_students_counts_the_skipped(course):
    c = course
    x = c.assignment(submission_type="none")
    c.put(
        "/grades",
        grades_body(x, {"student_id": c.student_id, "points": 5}, {"student_id": c.student2_id, "points": 6}),
        c.teacher,
    )
    body = {"item_type": "assignment", "item_id": x["id"], "student_ids": [c.student_id, c.student_b_id]}
    assert c.post("/grades/release", body, headers=c.teacher) == {"released": 1, "skipped": 1}
    assert c.post("/grades/release", {"item_type": "assignment", "item_id": x["id"]}, headers=c.teacher) == {
        "released": 1,
        "skipped": 0,
    }
    assert (
        c.call("POST", "/grades/release", {"item_type": "assignment", "item_id": new_id()}, c.teacher).status_code
        == 404
    )


def test_gradebook_statuses_and_unweighted_totals(course, org):
    c = course
    x = c.assignment(title="Essay")
    y = c.assignment(title="Lab", max_points=20, due_at=at(days=8))
    c.assignment(title="Draft", publish=False)
    c.post(f"/assignments/{x['id']}/submissions", {"text": "a"}, 201, c.student)
    c.post(f"/assignments/{y['id']}/submissions", {"text": "b"}, 201, c.student)
    c.post(f"/assignments/{x['id']}/submissions", {"text": "c"}, 201, c.student2)
    c.put("/grades", grades_body(x, {"student_id": c.student_id, "points": 8}), c.teacher)
    c.put("/grades", grades_body(y, {"student_id": c.student_id, "points": 10}), c.teacher)
    c.post("/grades/release", {"item_type": "assignment", "item_id": x["id"]}, headers=c.teacher)
    book = c.get(f"/course-spaces/{c.space['id']}/gradebook", c.teacher)
    assert [i["title"] for i in book["items"]] == ["Essay", "Lab"]
    rows = {s["student_id"]: s for s in book["students"]}
    assert set(rows) == {c.student_id, c.student2_id, c.student_b_id}
    asha = rows[c.student_id]
    assert asha["student_name"] == "Asha"
    assert [(cell["status"], cell["points"]) for cell in asha["cells"]] == [("released", 8), ("graded", 10)]
    assert (asha["released_points"], asha["released_max_points"], asha["released_percent"]) == (8, 10, 80.0)
    assert [cell["status"] for cell in rows[c.student2_id]["cells"]] == ["submitted", "missing"]
    assert rows[c.student_b_id]["released_percent"] is None
    # Who may read it.
    assert c.get(f"/course-spaces/{c.space['id']}/gradebook", c.admin)["course_space_id"] == c.space["id"]
    _, other_teacher = org.user(FACULTY)
    assert c.call("GET", f"/course-spaces/{c.space['id']}/gradebook", headers=other_teacher).status_code == 403
    _, head = org.user(HEAD)
    assert c.call("GET", f"/course-spaces/{c.space['id']}/gradebook", headers=head).status_code == 403  # LQ13
    assert c.call("GET", f"/course-spaces/{c.space['id']}/gradebook", headers=c.student).status_code == 403


def test_my_grades_only_released_and_only_mine(course):
    c = course
    x = c.assignment()
    c.put(
        "/grades",
        grades_body(x, {"student_id": c.student_id, "points": 5}, {"student_id": c.student2_id, "points": 6}),
        c.teacher,
    )
    c.post(
        "/grades/release",
        {"item_type": "assignment", "item_id": x["id"], "student_ids": [c.student2_id]},
        headers=c.teacher,
    )
    assert c.get("/me/grades", c.student)["items"] == []
    mine = c.get(f"/me/grades?course_space_id={c.space['id']}", c.student2)["items"]
    assert [g["points"] for g in mine[0]["grades"]] == [6]
    assert c.call("GET", "/me/grades?course_space_id=nope", headers=c.student2).status_code == 400
    assert c.call("GET", "/me/grades", headers=c.teacher).status_code == 403
