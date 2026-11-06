"""Assignments and submissions (FR-6, FR-7): lifecycle, the late policy, attempts, targeting, events and audit."""

from datetime import timedelta

from conftest import NOW, STUDENT, at, audit_actions, outbox, set_clock
from eos_lms.infrastructure.models import new_id


def test_assignment_lifecycle_and_events(course):
    c = course
    x = c.assignment(publish=False, instructions="Write 500 words")
    assert x["status"] == "draft" and x["late_policy"] == {"accept_late": False, "late_cutoff_at": None}
    assert c.call("GET", f"/assignments/{x['id']}", headers=c.student).status_code == 404
    assert c.get(f"/course-spaces/{c.space['id']}/assignments", c.student)["items"] == []
    # Editing a draft publishes nothing.
    c.patch(f"/assignments/{x['id']}", {"due_at": at(days=8)}, c.teacher)
    assert outbox("lms.assignment.updated", c.org.id) == []
    published = c.post(f"/assignments/{x['id']}/status", {"status": "published"}, headers=c.teacher)
    assert outbox("lms.assignment.published", c.org.id) == [
        {
            "organisation_id": c.org.id,
            "assignment_id": x["id"],
            "course_space_id": c.space["id"],
            "course_offering_id": c.offering,
            "title": "Essay 1",
            "due_at": at(days=8),
            "max_points": 10.0,
            "target_section_ids": [],
            "published_at": published["published_at"],
        }
    ]
    # A title change is not announced; a due date or late policy change is.
    c.patch(f"/assignments/{x['id']}", {"title": "Essay one"}, c.teacher)
    assert outbox("lms.assignment.updated", c.org.id) == []
    policy = {"accept_late": True, "late_cutoff_at": at(days=10)}
    c.patch(f"/assignments/{x['id']}", {"due_at": at(days=9), "late_policy": policy}, c.teacher)
    updated = outbox("lms.assignment.updated", c.org.id)
    assert updated[-1]["changed_fields"] == ["due_at", "late_policy"] and updated[-1]["status"] == "published"
    c.post(f"/assignments/{x['id']}/status", {"status": "closed"}, headers=c.teacher)
    assert outbox("lms.assignment.updated", c.org.id)[-1]["changed_fields"] == ["status"]
    r = c.call("PATCH", f"/assignments/{x['id']}", {"title": "x"}, c.teacher)
    assert r.status_code == 409
    r = c.call("POST", f"/assignments/{x['id']}/status", {"status": "published"}, c.teacher)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    assert c.get(f"/assignments/{x['id']}", c.student)["status"] == "closed"
    assert sorted(set(audit_actions(c.org.id, x["id"]))) == [
        "assignment.closed",
        "assignment.created",
        "assignment.published",
        "assignment.updated",
    ]


def test_assignment_validation(course):
    c = course
    base = f"/course-spaces/{c.space['id']}/assignments"
    good = {"title": "x", "due_at": at(days=1), "max_points": 5, "submission_type": "file"}
    for bad in (
        {**good, "max_points": 0},
        {**good, "max_points": -1},
        {**good, "max_points": 1e9},
        {**good, "max_attempts": 0},
        {**good, "max_attempts": 2**63},
        {**good, "submission_type": "video"},
        {**good, "due_at": "0001-01-01T00:00:00Z"},
        {**good, "late_policy": {"accept_late": True, "late_cutoff_at": at(hours=1)}},
        {**good, "late_policy": {"accept_late": False, "late_cutoff_at": at(days=3)}},
        {**good, "target_section_ids": ["A"]},
        {**good, "extra": 1},
    ):
        r = c.call("POST", base, bad, c.teacher)
        assert r.status_code == 400, (bad, r.text)
    assert c.call("POST", base, {**good, "unit_id": new_id()}, c.teacher).status_code == 422
    assert c.call("POST", base, good, c.student).status_code == 403
    assert c.call("POST", base, good, c.viewer).status_code == 403


def test_submissions_late_policy_and_attempts(course, monkeypatch):
    c = course
    x = c.assignment(max_attempts=2, late_policy={"accept_late": True, "late_cutoff_at": at(days=8)})
    path = f"/assignments/{x['id']}/submissions"
    first = c.post(path, {"text": "draft one"}, 201, c.student)
    assert (first["attempt"], first["late"], first["status"]) == (1, False, "submitted")
    assert outbox("lms.submission.submitted", c.org.id) == [
        {
            "organisation_id": c.org.id,
            "submission_id": first["id"],
            "assignment_id": x["id"],
            "course_space_id": c.space["id"],
            "student_id": c.student_id,
            "attempt": 1,
            "submitted_at": NOW.isoformat(),
            "late": False,
        }
    ]
    set_clock(monkeypatch, NOW + timedelta(days=7, hours=1))
    second = c.post(path, {"text": "final"}, 201, c.student)
    assert (second["attempt"], second["late"]) == (2, True)
    r = c.call("POST", path, {"text": "third"}, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_attempts_left"
    mine = c.get(f"/me/submissions?assignment_id={x['id']}", c.student)["items"]
    assert [(s["attempt"], s["status"]) for s in mine] == [(1, "superseded"), (2, "submitted")]
    listed = c.get(path, c.teacher)
    assert [s["id"] for s in listed["items"]] == [second["id"]] and listed["total"] == 1
    assert c.get(f"{path}?include_superseded=true", c.teacher)["total"] == 2
    assert c.get(f"{path}?status=superseded", c.teacher)["total"] == 1
    assert c.call("GET", f"{path}?include_superseded=maybe", headers=c.teacher).status_code == 400
    set_clock(monkeypatch, NOW + timedelta(days=8, minutes=1))
    r = c.call("POST", path, {"text": "late"}, c.student2)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "past_cutoff"


def test_no_late_work_unless_accepted(course, monkeypatch):
    c = course
    x = c.assignment()
    set_clock(monkeypatch, NOW + timedelta(days=7, seconds=1))
    r = c.call("POST", f"/assignments/{x['id']}/submissions", {"text": "late"}, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "past_due"


def test_submission_content_must_match_the_type(course):
    c = course
    doc = new_id()
    cases = {
        "file": [({"text": "x"}, 400), ({"document_ids": [doc], "text": "x"}, 400), ({"document_ids": [doc]}, 201)],
        "text": [({"document_ids": [doc]}, 400), ({"text": "  "}, 400), ({"text": "ok"}, 201)],
        "file_and_text": [({"text": "x"}, 400), ({"document_ids": [doc], "text": "x"}, 201)],
        "none": [({"text": "x"}, 409)],
    }
    for kind, attempts in cases.items():
        x = c.assignment(submission_type=kind, max_attempts=5)
        for body, status in attempts:
            r = c.call("POST", f"/assignments/{x['id']}/submissions", body, c.student)
            assert r.status_code == status, (kind, body, r.text)
    x = c.assignment()
    assert c.call("POST", f"/assignments/{x['id']}/submissions", {"text": "x" * 100_001}, c.student).status_code == 400
    many = {"document_ids": [new_id() for _ in range(21)]}
    assert c.call("POST", f"/assignments/{x['id']}/submissions", many, c.student).status_code == 400


def test_who_may_submit(course, org):
    c = course
    x = c.assignment(target_section_ids=[c.section_a])
    path = f"/assignments/{x['id']}/submissions"
    r = c.call("POST", path, {"text": "x"}, c.student_b)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_targeted"
    assert c.call("GET", f"/assignments/{x['id']}", headers=c.student_b).status_code == 404
    _, outsider = org.user(STUDENT)
    assert c.call("POST", path, {"text": "x"}, outsider).status_code == 403
    r = c.call("POST", path, {"text": "x"}, c.teacher)
    assert r.status_code == 403  # instructors do not hold submission:submit-own
    draft = c.assignment(publish=False)
    r = c.call("POST", f"/assignments/{draft['id']}/submissions", {"text": "x"}, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "assignment_not_published"
    c.post(f"/assignments/{x['id']}/status", {"status": "closed"}, headers=c.teacher)
    assert c.call("POST", path, {"text": "x"}, c.student).status_code == 409
    assert c.call("POST", f"/assignments/{new_id()}/submissions", {"text": "x"}, c.student).status_code == 404


def test_submissions_are_read_by_instructors_and_by_their_owner(course, org):
    c = course
    x = c.assignment()
    c.post(f"/assignments/{x['id']}/submissions", {"text": "mine"}, 201, c.student)
    assert c.call("GET", f"/assignments/{x['id']}/submissions", headers=c.student).status_code == 403
    from conftest import FACULTY

    _, stranger = org.user(FACULTY)
    r = c.call("GET", f"/assignments/{x['id']}/submissions", headers=stranger)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_in_scope"
    assert c.get(f"/assignments/{x['id']}/submissions", c.admin)["total"] == 1
    assert c.get("/me/submissions", c.student2)["items"] == []
    assert len(c.get(f"/me/submissions?course_space_id={c.space['id']}", c.student)["items"]) == 1


def test_assignment_max_points_cannot_drop_below_a_grade(course):
    c = course
    x = c.assignment()
    entry = {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": c.student_id, "points": 8}]}
    c.put("/grades", entry, c.teacher)
    r = c.call("PATCH", f"/assignments/{x['id']}", {"max_points": 5}, c.teacher)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "points_above_max"
    c.patch(f"/assignments/{x['id']}", {"max_points": 20}, c.teacher)
    book = c.get(f"/course-spaces/{c.space['id']}/gradebook", c.teacher)
    assert book["items"][0]["max_points"] == 20
