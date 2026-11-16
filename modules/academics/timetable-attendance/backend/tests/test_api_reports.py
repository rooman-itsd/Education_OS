"""Attendance reports end to end (FR-13, FR-14, FR-18): what counts, the active term, the department and read-all
scopes, and the exam-eligibility counts."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    ADMIN,
    BASE,
    EXAMS,
    HEAD,
    STUDENT,
    VIEWER,
    Classroom,
    active_term,
    allocate,
    ok,
)


def err(response, status: int) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()["detail"]


def classes_of(room: Classroom, *days: str) -> list[str]:
    return [f"2026-11-0{d}T09:00:00+00:00" for d in days]


@pytest.fixture
def term_room(client, org):
    """A classroom in an active term whose offering belongs to a department, with three students:
    A present, late, absent, excused (2 of 3 counted, 66.67); B present every time (100); C excused every time."""
    department = str(uuid.uuid4())
    room = Classroom(client, org, students=3, department_id=department)
    active_term(org.id, room.ids["period"])
    a, b, c = room.students
    for when, statuses in zip(
        (
            "2026-11-02T09:00:00+00:00",
            "2026-11-02T13:00:00+00:00",
            "2026-11-03T08:30:00+00:00",
            "2026-11-03T09:00:00+00:00",
        ),
        (
            {a: "present", b: "present", c: "excused"},
            {a: "late", b: "present", c: "excused"},
            {a: "absent", b: "present", c: "excused"},
            {a: "excused", b: "present", c: "excused"},
        ),
        strict=True,
    ):
        if when.startswith("2026-11-02"):
            cls = room.new_class(when)
            s = room.open(cls["id"], headers=room.admin)  # outside the faculty's window: override
            room.mark(s["id"], statuses, headers=room.admin)
            room.close(s["id"], headers=room.admin)
        else:
            room.held(statuses, when)
    # an open session and a cancelled class never count
    open_class = room.new_class("2026-11-03T09:30:00+00:00")
    s = room.open(open_class["id"], headers=room.admin)
    room.mark(s["id"], {a: "absent"}, headers=room.admin)
    cancelled = room.new_class("2026-11-03T08:45:00+00:00")
    s = room.open(cancelled["id"])
    room.mark(s["id"], {a: "absent"})
    ok(client.post(f"{BASE}/scheduled-classes/{cancelled['id']}/cancel", headers=room.admin))
    room.department = department
    return room


def student_headers(room: Classroom, student_id: str) -> dict:
    return room.org.user(STUDENT, user_id=student_id)[1]


def test_my_summary_counts_closed_sessions_and_leaves_excused_out(client, term_room):
    a, b, c = term_room.students
    mine = ok(client.get(f"{BASE}/me/attendance-summary", headers=student_headers(term_room, a)))
    assert (mine["student_id"], mine["academic_period_id"], mine["threshold_percent"]) == (
        a,
        term_room.ids["period"],
        75,
    )
    [item] = mine["items"]
    assert (item["classes_held"], item["attended"], item["excused"], item["percentage"], item["below_threshold"]) == (
        3,
        2,
        1,
        66.67,
        True,
    )
    assert (item["course_code"], item["course_title"], item["section_id"]) == (
        "CS101",
        "Programming",
        term_room.ids["section"],
    )
    assert mine["overall_percentage"] == 66.67
    full = ok(client.get(f"{BASE}/me/attendance-summary", headers=student_headers(term_room, b)))
    assert (full["items"][0]["percentage"], full["items"][0]["below_threshold"]) == (100.0, False)
    excused = ok(client.get(f"{BASE}/me/attendance-summary", headers=student_headers(term_room, c)))
    assert (
        excused["items"][0]["percentage"],
        excused["items"][0]["below_threshold"],
        excused["overall_percentage"],
    ) == (
        None,
        False,
        None,
    )


def test_without_an_active_term_the_summary_is_404_active_term_not_found(client, org):
    _, h = org.user(STUDENT)
    assert err(client.get(f"{BASE}/me/attendance-summary", headers=h), 404)["code"] == "active_term_not_found"
    period = str(uuid.uuid4())
    named = ok(client.get(f"{BASE}/me/attendance-summary?academic_period_id={period}", headers=h))
    assert (named["academic_period_id"], named["items"], named["overall_percentage"]) == (period, [], None)
    active_term(org.id, str(uuid.uuid4()), starts_on="2026-01-01", ends_on="2026-06-30")  # not today
    assert err(client.get(f"{BASE}/me/attendance-summary", headers=h), 404)["code"] == "active_term_not_found"
    assert err(client.get(f"{BASE}/me/attendance-summary?academic_period_id=x", headers=h), 400)["code"] == "invalid_id"


def test_my_history_is_newest_first_and_paged(client, term_room):
    a = term_room.students[0]
    h = student_headers(term_room, a)
    history = ok(client.get(f"{BASE}/me/attendance-history", headers=h))
    assert history["total"] == 4
    assert [i["status"] for i in history["items"]] == ["excused", "absent", "late", "present"]
    assert history["items"][0]["class_date"] == "2026-11-03" and history["items"][0]["course_code"] == "CS101"
    page = ok(client.get(f"{BASE}/me/attendance-history?limit=1&offset=1", headers=h))
    assert ([i["status"] for i in page["items"]], page["total"]) == (["absent"], 4)
    other = ok(client.get(f"{BASE}/me/attendance-history?course_offering_id={uuid.uuid4()}", headers=h))
    assert other == {"student_id": a, "items": [], "total": 0}
    assert client.get(f"{BASE}/me/attendance-history", headers=term_room.faculty).status_code == 403


def test_student_reports_need_read_all_until_the_department_is_known(client, term_room):
    a = term_room.students[0]
    _, viewer = term_room.org.user(VIEWER)
    _, head = term_room.org.user(HEAD)
    summary = ok(client.get(f"{BASE}/reports/students/{a}/attendance-summary", headers=viewer))
    assert summary["items"][0]["percentage"] == 66.67
    history = ok(client.get(f"{BASE}/reports/students/{a}/attendance-history?date_from=2026-11-03", headers=viewer))
    assert [i["status"] for i in history["items"]] == ["excused", "absent"]
    for url in (f"{BASE}/reports/students/{a}/attendance-summary", f"{BASE}/reports/students/{a}/attendance-history"):
        assert err(client.get(url, headers=head), 403)["code"] == "department_unknown"
        assert client.get(url, headers=term_room.faculty).status_code == 403
    r = client.get(
        f"{BASE}/reports/students/{a}/attendance-history?date_from=2026-11-04&date_to=2026-11-03", headers=viewer
    )
    assert err(r, 400)["code"] == "invalid_range"


def test_the_department_report_groups_by_offering_and_section(client, term_room):
    _, viewer = term_room.org.user(VIEWER)
    url = f"{BASE}/reports/department-attendance?department_id={term_room.department}"
    report = ok(client.get(url, headers=viewer))
    assert (report["department_id"], report["academic_period_id"], report["date_from"], report["date_to"]) == (
        term_room.department,
        term_room.ids["period"],
        None,
        None,
    )
    [row] = report["items"]
    assert (row["course_code"], row["section_code"], row["instructor_id"], row["classes_held"]) == (
        "CS101",
        "A",
        term_room.instructor_id,
        4,
    )
    assert (row["average_percentage"], row["students_below_threshold"], "students" in row) == (83.34, 1, False)
    assert report["overall_percentage"] == 85.71  # 6 attended of 7 counted
    listed = ok(client.get(url + "&include_students_below_threshold=true", headers=viewer))
    assert listed["items"][0]["students"] == [
        {"student_id": term_room.students[0], "student_name": "Student 0", "percentage": 66.67}
    ]
    ranged = ok(client.get(url + "&date_from=2026-11-03&date_to=2026-11-03", headers=viewer))
    assert ranged["items"][0]["classes_held"] == 2 and ranged["date_from"] == "2026-11-03"
    empty = ok(client.get(f"{BASE}/reports/department-attendance?department_id={uuid.uuid4()}", headers=viewer))
    assert (empty["items"], empty["overall_percentage"]) == ([], None)
    assert err(client.get(url + "&include_students_below_threshold=maybe", headers=viewer), 400)["code"] == (
        "invalid_boolean"
    )


def test_the_department_report_scopes(client, org, term_room):
    _, viewer = term_room.org.user(VIEWER)
    _, head = term_room.org.user(HEAD)
    url = f"{BASE}/reports/department-attendance"
    assert err(client.get(url, headers=viewer), 400)["code"] == "department_required"
    assert err(client.get(url, headers=head), 403)["code"] == "department_unknown"
    assert err(client.get(f"{url}?department_id={term_room.department}", headers=head), 403)["code"] == (
        "department_unknown"
    )
    assert client.get(url, headers=term_room.faculty).status_code == 403


def test_a_new_organisations_department_head_gets_active_term_not_found(client, other_org):
    _, head = other_org.user(HEAD)
    detail = err(client.get(f"{BASE}/reports/department-attendance", headers=head), 404)
    assert detail["code"] == "active_term_not_found"


def test_eligibility_counts_per_student_up_to_the_cutoff(client, term_room):
    _, exams = term_room.org.user(EXAMS)
    a, b, c = term_room.students
    stranger = str(uuid.uuid4())
    body = {"course_offering_id": term_room.ids["offering"], "cutoff_date": "2026-11-03"}
    report = ok(client.post(f"{BASE}/reports/attendance-eligibility", json=body, headers=exams))
    assert report["open_sessions_excluded"] == 1 and report["unknown_student_ids"] == []
    assert report["generated_at"] == "2026-11-03T09:00:00+00:00" and report["from_date"] is None
    by = {i["student_id"]: i for i in report["items"]}
    assert set(by) == {a, b, c}
    assert {k: by[a][k] for k in ("classes_counted", "attended", "absent", "excused", "no_eligible_classes")} == {
        "classes_counted": 3,
        "attended": 2,
        "absent": 1,
        "excused": 1,
        "no_eligible_classes": False,
    }
    assert (by[c]["classes_counted"], by[c]["no_eligible_classes"]) == (0, True)
    asked = ok(
        client.post(
            f"{BASE}/reports/attendance-eligibility",
            json={**body, "cutoff_date": "2026-11-02", "student_ids": [b, stranger]},
            headers=exams,
        )
    )
    assert ([i["student_id"] for i in asked["items"]], asked["unknown_student_ids"]) == ([b], [stranger])
    assert asked["items"][0]["classes_counted"] == 2 and asked["open_sessions_excluded"] == 0
    late = allocate(term_room.org.id, term_room.ids["section"], since="2026-11-10")
    later = ok(
        client.post(
            f"{BASE}/reports/attendance-eligibility",
            json={**body, "from_date": "2026-11-03", "student_ids": [late]},
            headers=exams,
        )
    )
    assert later["unknown_student_ids"] == [late]


def test_eligibility_refuses_bad_input_and_unknown_offerings(client, org):
    _, exams = org.user(EXAMS)
    url = f"{BASE}/reports/attendance-eligibility"
    offering = str(uuid.uuid4())
    assert err(client.post(url, json={"course_offering_id": offering}, headers=exams), 400)["code"] == "missing_field"
    body = {"course_offering_id": offering, "cutoff_date": "2026-11-03"}
    assert err(client.post(url, json=body, headers=exams), 404)["code"] == "unknown_course_offering"
    bad = {**body, "from_date": "2026-11-04"}
    assert err(client.post(url, json=bad, headers=exams), 400)["code"] == "invalid_range"
    many = {**body, "student_ids": [str(uuid.uuid4()) for _ in range(2001)]}
    assert err(client.post(url, json=many, headers=exams), 400)["code"] == "too_many_students"
    _, admin = org.user(ADMIN)
    _, student = org.user(STUDENT)
    assert client.post(url, json=body, headers=student).status_code == 403
    assert client.post(url, json=body, headers=admin).status_code == 404  # admin holds read-eligibility
