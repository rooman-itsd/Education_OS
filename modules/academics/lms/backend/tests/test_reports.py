"""The coursework activity report (FR-18)."""

from datetime import timedelta

from conftest import HEAD, NOW, Course, set_clock
from eos_lms.infrastructure.models import new_id


def test_activity_per_course_space(client, org, monkeypatch):
    c = Course(client, org)
    other = Course(client, org, period_id=c.period)
    c.material()
    c.material("Draft", publish=False)
    x = c.assignment()
    c.quiz()
    set_clock(monkeypatch, NOW + timedelta(hours=2))
    c.post(f"/assignments/{x['id']}/submissions", {"text": "a"}, 201, c.student)
    set_clock(monkeypatch, NOW + timedelta(hours=3))
    c.post(f"/assignments/{x['id']}/submissions", {"text": "b"}, 201, c.student2)
    c.put(
        "/grades",
        {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": c.student2_id, "points": 4}]},
        c.teacher,
    )
    set_clock(monkeypatch, NOW + timedelta(hours=4))
    c.post(f"/course-spaces/{c.space['id']}/threads", {"title": "Q", "body": "?"}, 201, c.student)
    report = c.get("/reports/coursework-activity", c.viewer)
    assert report["department_id"] is None
    rows = {r["course_space_id"]: r for r in report["items"]}
    mine = rows[c.space["id"]]
    assert mine == {
        "course_space_id": c.space["id"],
        "course_offering_id": c.offering,
        "course_title": "Programming",
        "materials_published": 1,
        "assignments_published": 1,
        "quizzes_published": 1,
        "submissions_received": 2,
        "ungraded": 1,
        "oldest_ungraded_since": (NOW + timedelta(hours=2)).isoformat(),
        "last_activity_at": (NOW + timedelta(hours=4)).isoformat(),
    }
    assert rows[other.space["id"]]["submissions_received"] == 0 and rows[other.space["id"]]["last_activity_at"] is None
    by_department = c.get(f"/reports/coursework-activity?department_id={c.department}", c.admin)
    assert by_department["department_id"] == c.department
    assert [r["course_space_id"] for r in by_department["items"]] == [c.space["id"]]
    by_period = c.get(f"/reports/coursework-activity?academic_period_id={c.period}", c.admin)
    assert {r["course_space_id"] for r in by_period["items"]} == {c.space["id"], other.space["id"]}
    assert c.get(f"/reports/coursework-activity?academic_period_id={new_id()}", c.admin)["items"] == []


def test_department_scope_waits_for_the_callers_department(course, org):
    c = course
    _, head = org.user(HEAD)
    assert c.get("/reports/coursework-activity", head) == {"department_id": None, "items": []}
    r = c.call("GET", f"/reports/coursework-activity?department_id={c.department}", headers=head)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "department_unverified"
    assert c.call("GET", "/reports/coursework-activity", headers=c.teacher).status_code == 403
    assert c.call("GET", "/reports/coursework-activity?department_id=x", headers=c.admin).status_code == 400
