"""Cross-tenant isolation of classes, attendance and reports (module standard rule 11, FR-15): one organisation never
lists, reads, changes or counts another's classes, sessions or records, and the attendance queries return nothing
without an organisation on the session."""

import uuid
from datetime import date

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, EXAMS, STUDENT, VIEWER, Classroom, active_term, ok, outbox  # noqa: E402
from eos_testing import assert_no_cross_tenant_leak  # noqa: E402


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def held_room(client, org) -> tuple[Classroom, dict, dict, str]:
    room = Classroom(client, org, students=1, department_id=str(uuid.uuid4()))
    active_term(org.id, room.ids["period"])
    c, s = room.held({room.students[0]: "absent"})
    record = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))["items"][0]
    return room, c, s, record["id"]


def test_no_cross_tenant_leak_in_the_class_list(client, org, other_org):
    mine, _, _, _ = held_room(client, org)
    theirs, _, _, _ = held_room(client, other_org)
    assert_no_cross_tenant_leak(client, f"{BASE}/scheduled-classes", token(mine.admin), token(theirs.admin))


def test_another_organisations_ids_are_not_found_on_every_operation(client, org, other_org):
    mine, _, _, _ = held_room(client, org)
    theirs, c, s, record_id = held_room(client, other_org)
    open_class = theirs.new_class("2026-11-03T09:10:00+00:00")
    open_session = theirs.open(open_class["id"])
    h = mine.admin
    calls = [
        client.get(f"{BASE}/scheduled-classes/{c['id']}", headers=h),
        client.patch(f"{BASE}/scheduled-classes/{open_class['id']}", json={"location_label": "x"}, headers=h),
        client.post(f"{BASE}/scheduled-classes/{open_class['id']}/cancel", headers=h),
        client.get(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=h),
        client.post(f"{BASE}/scheduled-classes/{open_class['id']}/attendance-session", headers=h),
        client.get(f"{BASE}/attendance-sessions/{s['id']}", headers=h),
        client.post(f"{BASE}/attendance-sessions/{open_session['id']}/close", headers=h),
        client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=h),
        client.put(
            f"{BASE}/attendance-sessions/{open_session['id']}/records",
            json={"records": [{"student_id": theirs.students[0], "status": "present"}]},
            headers=h,
        ),
        client.patch(f"{BASE}/attendance-records/{record_id}", json={"status": "present", "reason": "x"}, headers=h),
        client.get(f"{BASE}/attendance-records/{record_id}/history", headers=h),
    ]
    for response in calls:
        assert response.status_code == 404, response.text
    still = ok(client.get(f"{BASE}/scheduled-classes/{open_class['id']}", headers=theirs.admin))
    assert (still["status"], still["location_label"], still["attendance_session"]["status"]) == (
        "scheduled",
        None,
        "open",
    )


def test_reports_and_me_reads_count_only_their_own_organisation(client, org, other_org):
    mine, _, _, _ = held_room(client, org)
    theirs, _, _, _ = held_room(client, other_org)
    shared_student = theirs.students[0]
    # the same person id in another organisation sees nothing of it
    h = org.user(STUDENT, user_id=shared_student)[1]
    assert ok(client.get(f"{BASE}/me/attendance-history", headers=h)) == {
        "student_id": shared_student,
        "items": [],
        "total": 0,
    }
    assert ok(client.get(f"{BASE}/me/schedule", headers=h))["items"] == []
    _, viewer = org.user(VIEWER)
    summary = ok(
        client.get(
            f"{BASE}/reports/students/{shared_student}/attendance-summary?academic_period_id={theirs.ids['period']}",
            headers=viewer,
        )
    )
    assert summary["items"] == []
    department = ok(
        client.get(
            f"{BASE}/reports/department-attendance?department_id={uuid.uuid4()}&academic_period_id={theirs.ids['period']}",
            headers=viewer,
        )
    )
    assert department["items"] == []
    other_faculty = org.user("timetable-attendance-faculty", user_id=theirs.instructor_id)[1]
    assert ok(client.get(f"{BASE}/me/teaching-schedule", headers=other_faculty))["items"] == []
    exams = org.user(EXAMS)[1]
    r = client.post(
        f"{BASE}/reports/attendance-eligibility",
        json={"course_offering_id": theirs.ids["offering"], "cutoff_date": "2026-11-03"},
        headers=exams,
    )
    assert r.status_code == 404
    for name in (
        "timetable-attendance.scheduled-class.created",
        "timetable-attendance.attendance-session.opened",
        "timetable-attendance.attendance-session.closed",
    ):
        assert all(e["organisation_id"] == org.id for e in outbox(name, org.id))
    assert mine.org.id != theirs.org.id


def test_attendance_queries_match_nothing_without_an_organisation(client, org):
    from eos_core.db import SessionLocal
    from eos_timetable_attendance.infrastructure import attendance_repository as ar

    room, c, s, record_id = held_room(client, org)
    with SessionLocal() as db:  # no organisation on the session
        assert ar.scheduled_class(db, c["id"]) is None
        assert ar.session(db, s["id"]) is None
        assert ar.record(db, record_id) is None
        assert ar.classes(db, limit=10, offset=0) == ([], 0)
        assert ar.attendance(db) == []
        assert ar.active_term(db, date(2026, 11, 3)) is None
        assert ar.members_on(db, room.ids["section"], date(2026, 11, 3)) == []
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        assert ar.scheduled_class(db, c["id"]).id == c["id"]
        assert len(ar.attendance(db)) == 1
