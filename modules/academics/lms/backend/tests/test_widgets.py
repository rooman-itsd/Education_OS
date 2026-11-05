"""The two dashboard endpoints: GET /me/grading-queue (lms.assignments-to-grade, Faculty) and GET /me/course-materials
(lms.course-materials, Student), FR-16 and FR-17."""

from datetime import timedelta

from conftest import BASE, FACULTY, NOW, STUDENT, Course, at, deliver, ok, set_clock
from eos_lms.application import consumers as cons
from eos_lms.infrastructure.models import new_id


def test_course_materials_lists_published_materials_newest_first(course, monkeypatch):
    c = course
    first = c.material("Syllabus")
    set_clock(monkeypatch, NOW + timedelta(hours=1))
    second = c.material("Week 1 slides", material_type="link", url="https://example.org/w1", body=None)
    c.material("Draft only", publish=False)
    items = c.get("/me/course-materials", c.student)["items"]
    assert [i["material_id"] for i in items] == [second["id"], first["id"]]
    assert items[0] == {
        "material_id": second["id"],
        "course_space_id": c.space["id"],
        "course_title": "Programming",
        "title": "Week 1 slides",
        "material_type": "link",
        "published_at": (NOW + timedelta(hours=1)).isoformat(),
    }
    assert [i["material_id"] for i in c.get("/me/course-materials?limit=1", c.student)["items"]] == [second["id"]]


def test_course_materials_respects_sections_units_and_the_window(course, monkeypatch):
    c = course
    only_b = c.material("Section B only", visible_section_ids=[c.section_b])
    unit = c.post(f"/course-spaces/{c.space['id']}/units", {"title": "Week 2"}, 201, c.teacher)
    hidden_unit = c.material("In a hidden unit", unit_id=unit["id"])
    everyone = c.material("Everyone")
    mine = {i["material_id"] for i in c.get("/me/course-materials", c.student)["items"]}
    assert mine == {everyone["id"]}
    theirs = {i["material_id"] for i in c.get("/me/course-materials", c.student_b)["items"]}
    assert theirs == {everyone["id"], only_b["id"]}
    c.patch(f"/units/{unit['id']}", {"published": True}, c.teacher)
    assert hidden_unit["id"] in {i["material_id"] for i in c.get("/me/course-materials", c.student)["items"]}
    # Older than 14 days drops out by default; `since` reaches further back.
    set_clock(monkeypatch, NOW + timedelta(days=15))
    assert c.get("/me/course-materials", c.student)["items"] == []
    since = (NOW - timedelta(days=1)).isoformat().replace("+", "%2B")
    assert len(c.get(f"/me/course-materials?since={since}", c.student)["items"]) == 2
    # The instructor sees everything they published, whatever the section.
    assert len(c.get(f"/me/course-materials?since={since}", c.teacher)["items"]) == 3


def test_course_materials_only_from_active_spaces_the_caller_belongs_to(client, org, course):
    c = course
    c.material("Notes")
    outsider_id, outsider = org.user(STUDENT)
    assert c.get("/me/course-materials", outsider)["items"] == []
    c.post(f"/course-spaces/{c.space['id']}/status", {"status": "archived"})
    assert c.get("/me/course-materials", c.student)["items"] == []


def test_course_materials_parameters_are_bounded(course):
    c = course
    for bad in ("0", "51", "-1", "1e3", "٣", "99999999999999999999"):
        r = c.call("GET", f"/me/course-materials?limit={bad}", headers=c.student)
        assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_parameter", bad
    for bad in ("yesterday", "0001-01-01T00:00:00", "9999-12-31T23:59:59-05:00"):
        assert c.call("GET", f"/me/course-materials?since={bad}", headers=c.student).status_code == 400, bad
    assert c.call("GET", "/me/course-materials?limit=50", headers=c.student).status_code == 200


def test_grading_queue_counts_waiting_work_oldest_first(course, monkeypatch):
    c = course
    essay = c.assignment(title="Essay")
    lab = c.assignment(title="Lab", due_at=at(days=3))
    c.assignment(title="Not yet published", publish=False)
    set_clock(monkeypatch, NOW + timedelta(hours=1))
    c.post(f"/assignments/{essay['id']}/submissions", {"text": "mine"}, 201, c.student)
    set_clock(monkeypatch, NOW + timedelta(hours=2))
    c.post(f"/assignments/{lab['id']}/submissions", {"text": "lab"}, 201, c.student)
    c.post(f"/assignments/{essay['id']}/submissions", {"text": "theirs"}, 201, c.student2)
    q = c.get("/me/grading-queue", c.teacher)
    assert q["total"] == 2
    assert [(i["title"], i["waiting_count"]) for i in q["items"]] == [("Essay", 2), ("Lab", 1)]
    assert q["items"][0]["oldest_waiting_since"] == (NOW + timedelta(hours=1)).isoformat()
    assert q["items"][0]["course_title"] == "Programming" and q["items"][0]["item_type"] == "assignment"
    # Grading the essay for both students empties it from the queue.
    entries = [{"student_id": c.student_id, "points": 8}, {"student_id": c.student2_id, "points": 7}]
    c.put("/grades", {"item_type": "assignment", "item_id": essay["id"], "entries": entries}, c.teacher)
    assert [i["title"] for i in c.get("/me/grading-queue", c.teacher)["items"]] == ["Lab"]


def test_grading_queue_includes_quizzes_waiting_for_essay_scores(course):
    c = course
    qz = c.quiz(
        questions=[
            {"question_type": "essay", "prompt": "Explain recursion", "points": 5},
            {"question_type": "true_false", "prompt": "1 is odd", "answer_key": True, "points": 1},
        ]
    )
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    c.post(f"/attempts/{attempt['id']}/submit", None, headers=c.student)
    items = c.get("/me/grading-queue", c.teacher)["items"]
    assert [(i["item_type"], i["item_id"], i["waiting_count"]) for i in items] == [("quiz", qz["id"], 1)]
    assert items[0]["due_at"] == qz["closes_at"]


def test_grading_queue_is_only_for_the_spaces_the_caller_teaches(client, org, course):
    c = course
    x = c.assignment()
    c.post(f"/assignments/{x['id']}/submissions", {"text": "mine"}, 201, c.student)
    _, other_teacher = org.user(FACULTY)
    assert c.get("/me/grading-queue", other_teacher) == {"items": [], "total": 0}
    # An LMS administrator teaches nothing; the queue is about the caller's own teaching.
    assert c.get("/me/grading-queue", c.admin) == {"items": [], "total": 0}
    assert c.call("GET", "/me/grading-queue", headers=c.student).status_code == 403
    # An instructor whose assignment ended no longer sees the space's queue.
    ended = {
        "instructor_assignment_id": new_id(),
        "course_offering_id": c.offering,
        "section_id": None,
        "faculty_id": c.teacher_id,
        "ended_at": NOW.isoformat(),
    }
    deliver(org.id, cons.ASSIGNMENT_ENDED, ended)  # a different assignment: still teaching
    assert c.get("/me/grading-queue", c.teacher)["total"] == 1


def test_widget_endpoints_need_a_token_and_the_key(client, course):
    for path in ("/me/grading-queue", "/me/course-materials"):
        assert client.get(f"{BASE}{path}").status_code == 401
        assert client.get(f"{BASE}{path}", headers={"Authorization": "Bearer nope"}).status_code == 401
    _, nobody = course.org.user("applicant")
    assert course.call("GET", "/me/course-materials", headers=nobody).status_code == 403
    assert course.call("GET", "/me/grading-queue", headers=course.viewer).status_code == 403


def test_roles_extending_student_and_faculty_use_the_widgets(client, org):
    """teacher-trainee extends student and mentor-teacher extends faculty (docs/prd.md section 4)."""
    c = Course(client, org)
    trainee_id, trainee = c.enrol(c.section_a, "Deepa", role="teacher-trainee")
    mentor_id, mentor = org.user("mentor-teacher")
    deliver(org.id, cons.ASSIGNMENT_CREATED, {**_assignment(c.offering, mentor_id)})
    c.material("Lesson plan template")
    assert len(ok(client.get(f"{BASE}/me/course-materials", headers=trainee))["items"]) == 1
    x = c.assignment()
    c.post(f"/assignments/{x['id']}/submissions", {"text": "plan"}, 201, trainee)
    assert ok(client.get(f"{BASE}/me/grading-queue", headers=mentor))["total"] == 1


def _assignment(offering_id: str, faculty_id: str) -> dict:
    return {
        "instructor_assignment_id": new_id(),
        "course_offering_id": offering_id,
        "section_id": None,
        "faculty_id": faculty_id,
        "role": "co_instructor",
        "contact_hours": 1,
    }
