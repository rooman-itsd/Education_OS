"""Scheduled classes end to end (FR-5): ad-hoc creation, listing and filters, rescheduling and cancelling."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    ADMIN,
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    Classroom,
    audit_entries,
    make_class,
    ok,
    outbox,
)


def err(response, status: int) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()["detail"]


def test_an_adhoc_class_takes_its_period_and_instructor_from_the_read_models(client, org):
    instructor = str(uuid.uuid4())
    ids = org.academic(instructor_id=instructor)
    _, h = org.user(HEAD)
    c = make_class(client, h, ids, "2026-11-09T09:30:00+05:30", ends="2026-11-09T10:30:00+05:30", location_label=" R1 ")
    assert (c["slot_id"], c["timetable_id"], c["status"], c["cancel_reason"]) == (None, None, "scheduled", None)
    assert (c["academic_period_id"], c["instructor_id"], c["organisation_id"]) == (ids["period"], instructor, org.id)
    assert (c["starts_at"], c["ends_at"]) == ("2026-11-09T04:00:00+00:00", "2026-11-09T05:00:00+00:00")
    assert (c["class_date"], c["location_label"], c["attendance_session"]) == ("2026-11-09", "R1", None)
    assert (c["course_code"], c["course_title"], c["section_code"]) == ("CS101", "Programming", "A")
    assert ok(client.get(f"{BASE}/scheduled-classes/{c['id']}", headers=h)) == c
    [event] = [
        e for e in outbox("timetable-attendance.scheduled-class.created", org.id) if e["scheduled_class_id"] == c["id"]
    ]
    assert (event["instructor_id"], event["class_date"], event["timetable_id"]) == (instructor, "2026-11-09", None)
    [entry] = audit_entries(org.id, c["id"])
    assert (entry.action, entry.before, entry.after["class_date"]) == ("scheduled-class.created", None, "2026-11-09")


def test_the_class_date_is_read_in_the_offset_the_request_gives(client, org):
    ids = org.academic()
    _, h = org.user(ADMIN)
    late = make_class(client, h, ids, "2026-11-09T23:30:00-05:00", ends="2026-11-10T00:30:00-05:00")
    assert (late["class_date"], late["starts_at"]) == ("2026-11-09", "2026-11-10T04:30:00+00:00")


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"starts_at": "2026-11-09T09:00:00"}, 400, "invalid_datetime"),
        ({"ends_at": "2026-11-09T08:00:00+00:00"}, 400, "invalid_class_times"),
        ({"course_offering_id": "nope"}, 400, "invalid_id"),
        ({"colour": "red"}, 400, "unknown_field"),
        ({"section_id": None}, 400, "invalid_id"),
        ({"section_id": str(uuid.uuid4())}, 422, "unknown_section"),
        ({"instructor_assignment_id": str(uuid.uuid4())}, 422, "unknown_instructor_assignment"),
        ({"course_offering_id": str(uuid.uuid4())}, 422, "unknown_course_offering"),
    ],
)
def test_create_refuses_bad_or_unknown_input(client, org, change, status, code):
    ids = org.academic()
    _, h = org.user(ADMIN)
    body = {
        "course_offering_id": ids["offering"],
        "section_id": ids["section"],
        "instructor_assignment_id": ids["assignment"],
        "starts_at": "2026-11-09T09:00:00+00:00",
        "ends_at": "2026-11-09T10:00:00+00:00",
        **change,
    }
    assert err(client.post(f"{BASE}/scheduled-classes", json=body, headers=h), status)["code"] == code
    assert ok(client.get(f"{BASE}/scheduled-classes", headers=h))["total"] == 0


def test_create_needs_every_required_field_and_a_body_object(client, org):
    _, h = org.user(ADMIN)
    assert err(client.post(f"{BASE}/scheduled-classes", json={}, headers=h), 400)["code"] == "missing_field"
    assert err(client.post(f"{BASE}/scheduled-classes", json=[1], headers=h), 400)["code"] == "invalid_body"


def test_only_writers_create_and_only_readers_list(client, org):
    ids = org.academic()
    _, faculty = org.user(FACULTY)
    _, student = org.user(STUDENT)
    body = {"course_offering_id": ids["offering"]}
    assert err(client.post(f"{BASE}/scheduled-classes", json=body, headers=faculty), 403)["code"] == "forbidden"
    assert client.get(f"{BASE}/scheduled-classes", headers=student).status_code == 403
    assert client.get(f"{BASE}/scheduled-classes", headers=faculty).status_code == 200


def test_list_orders_by_start_and_filters(client, org):
    room = Classroom(client, org, students=0, department_id=(dept := str(uuid.uuid4())))
    other = org.academic()
    second = room.new_class("2026-11-10T09:00:00+00:00")
    first = room.new_class("2026-11-09T09:00:00+00:00")
    elsewhere = make_class(client, room.admin, other, "2026-11-09T11:00:00+00:00")
    h = room.admin

    def listed(query: str = "") -> list[str]:
        return [c["id"] for c in ok(client.get(f"{BASE}/scheduled-classes?{query}", headers=h))["items"]]

    assert listed() == [first["id"], elsewhere["id"], second["id"]]
    assert listed("date_from=2026-11-10") == [second["id"]]
    assert listed("date_to=2026-11-09") == [first["id"], elsewhere["id"]]
    assert listed(f"course_offering_id={other['offering']}") == [elsewhere["id"]]
    assert listed(f"section_id={room.ids['section']}") == [first["id"], second["id"]]
    assert listed(f"instructor_id={room.instructor_id}") == [first["id"], second["id"]]
    assert listed(f"department_id={dept}") == [first["id"], second["id"]]
    assert listed(f"department_id={uuid.uuid4()}") == []
    assert listed(f"academic_period_id={other['period']}") == [elsewhere["id"]]
    assert listed("status=cancelled") == []
    assert listed(f"timetable_id={uuid.uuid4()}") == []
    page = ok(client.get(f"{BASE}/scheduled-classes?limit=1&offset=1", headers=h))
    assert (page["total"], [c["id"] for c in page["items"]]) == (3, [elsewhere["id"]])
    assert err(client.get(f"{BASE}/scheduled-classes?status=done", headers=h), 400)["code"] == "invalid_choice"
    assert (
        err(client.get(f"{BASE}/scheduled-classes?date_from=2026-11-10&date_to=2026-11-09", headers=h), 400)["code"]
        == "invalid_range"
    )
    assert err(client.get(f"{BASE}/scheduled-classes?section_id=x", headers=h), 400)["code"] == "invalid_id"


def test_get_an_unknown_class_is_404(client, org):
    _, h = org.user(ADMIN)
    assert (
        err(client.get(f"{BASE}/scheduled-classes/{uuid.uuid4()}", headers=h), 404)["code"]
        == "scheduled_class_not_found"
    )


def test_reschedule_keeps_the_id_and_records_the_old_time(client, room):
    c = room.new_class("2026-11-09T09:00:00+00:00")
    body = {"starts_at": "2026-11-11T14:00:00+05:30", "ends_at": "2026-11-11T15:00:00+05:30", "reason": "exam hall"}
    moved = ok(client.patch(f"{BASE}/scheduled-classes/{c['id']}", json=body, headers=room.admin))
    assert (moved["id"], moved["class_date"], moved["starts_at"]) == (
        c["id"],
        "2026-11-11",
        "2026-11-11T08:30:00+00:00",
    )
    [event] = [
        e
        for e in outbox("timetable-attendance.scheduled-class.updated", room.org.id)
        if e["scheduled_class_id"] == c["id"]
    ]
    assert (event["changed_fields"], event["class_date"]) == (["starts_at", "ends_at"], "2026-11-11")
    [entry] = [e for e in audit_entries(room.org.id, c["id"]) if e.action == "scheduled-class.updated"]
    assert (entry.action, entry.reason) == ("scheduled-class.updated", "exam hall")
    assert (entry.before["starts_at"], entry.before["class_date"]) == ("2026-11-09T09:00:00+00:00", "2026-11-09")
    assert entry.after["class_date"] == "2026-11-11"


def test_location_and_a_substitute_instructor_change(client, room):
    c = room.new_class()
    substitute = str(uuid.uuid4())
    assignment = str(uuid.uuid4())
    from eos_core.db import SessionLocal
    from eos_timetable_attendance.infrastructure.models import AssignmentRef

    with SessionLocal() as db:
        db.add(
            AssignmentRef(
                organisation_id=room.org.id,
                instructor_assignment_id=assignment,
                course_offering_id=room.ids["offering"],
                section_id=room.ids["section"],
                instructor_id=substitute,
                status="active",
            )
        )
        db.commit()
    body = {"location_label": "Lab 2", "instructor_assignment_id": assignment}
    changed = ok(client.patch(f"{BASE}/scheduled-classes/{c['id']}", json=body, headers=room.admin))
    assert (changed["location_label"], changed["instructor_id"]) == ("Lab 2", substitute)
    cleared = ok(client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"location_label": None}, headers=room.admin))
    assert cleared["location_label"] is None
    events = [
        e
        for e in outbox("timetable-attendance.scheduled-class.updated", room.org.id)
        if e["scheduled_class_id"] == c["id"]
    ]
    assert [e["changed_fields"] for e in events] == [["location_label", "instructor_assignment_id"], ["location_label"]]
    other = room.org.academic()
    r = client.patch(
        f"{BASE}/scheduled-classes/{c['id']}",
        json={"instructor_assignment_id": other["assignment"]},
        headers=room.admin,
    )
    assert err(r, 422)["code"] == "assignment_mismatch"


def test_a_change_that_alters_nothing_publishes_and_audits_nothing(client, room):
    c = room.new_class()
    before = len(audit_entries(room.org.id, c["id"]))
    same = ok(
        client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"starts_at": c["starts_at"]}, headers=room.admin)
    )
    assert same == c
    assert len(audit_entries(room.org.id, c["id"])) == before


def test_cancel_records_the_reason_and_blocks_further_changes(client, room):
    c = room.new_class()
    cancelled = ok(
        client.post(f"{BASE}/scheduled-classes/{c['id']}/cancel", json={"reason": "holiday"}, headers=room.admin)
    )
    assert (cancelled["status"], cancelled["cancel_reason"]) == ("cancelled", "holiday")
    [event] = [
        e
        for e in outbox("timetable-attendance.scheduled-class.cancelled", room.org.id)
        if e["scheduled_class_id"] == c["id"]
    ]
    assert (event["reason"], event["class_date"]) == ("holiday", c["class_date"])
    assert (
        err(client.post(f"{BASE}/scheduled-classes/{c['id']}/cancel", headers=room.admin), 409)["code"]
        == "class_cancelled"
    )
    r = client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"location_label": "x"}, headers=room.admin)
    assert err(r, 409)["code"] == "class_cancelled"
    assert client.post(f"{BASE}/scheduled-classes/{c['id']}/cancel", headers=room.faculty).status_code == 403


def test_a_class_with_a_closed_session_cannot_change_or_be_cancelled(client, room):
    c, _ = room.held({room.students[0]: "present"})
    r = client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"location_label": "x"}, headers=room.admin)
    assert err(r, 409)["code"] == "attendance_closed"
    assert (
        err(client.post(f"{BASE}/scheduled-classes/{c['id']}/cancel", headers=room.admin), 409)["code"]
        == "attendance_closed"
    )


def test_cancelling_a_class_with_an_open_session_cancels_the_session_without_absences(client, room):
    c = room.new_class()
    s = room.open(c["id"])
    room.mark(s["id"], {room.students[0]: "present"})
    cancelled = ok(client.post(f"{BASE}/scheduled-classes/{c['id']}/cancel", headers=room.admin))
    assert cancelled["attendance_session"] == {"id": s["id"], "status": "cancelled"}
    session = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}", headers=room.faculty))
    assert (session["status"], session["closed_at"], session["counts"]["absent"], session["counts"]["unmarked"]) == (
        "cancelled",
        None,
        0,
        2,
    )
    assert err(room.client.post(f"{BASE}/attendance-sessions/{s['id']}/close", headers=room.faculty), 409)["code"] == (
        "session_cancelled"
    )
    r = client.put(
        f"{BASE}/attendance-sessions/{s['id']}/records",
        json={"records": [{"student_id": room.students[1], "status": "late"}]},
        headers=room.faculty,
    )
    assert err(r, 409)["code"] == "session_cancelled"
    assert not outbox("timetable-attendance.attendance-session.closed", room.org.id)
    assert "attendance-session.cancelled" in {e.action for e in audit_entries(room.org.id, s["id"])}
