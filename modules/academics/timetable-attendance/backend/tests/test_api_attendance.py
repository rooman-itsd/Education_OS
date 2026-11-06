"""Attendance sessions and records end to end (FR-7 to FR-12): open, mark, close, correct, history, and the scopes
of the instructor, the override holder and everyone else. The frozen clock is 2026-11-03 09:00 UTC."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    ADMIN,
    BASE,
    FACULTY,
    HEAD,
    VIEWER,
    Classroom,
    allocate,
    audit_entries,
    ok,
    outbox,
)


def err(response, status: int) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()["detail"]


def test_opening_snapshots_the_students_allocated_on_the_class_date(client, org):
    room = Classroom(client, org, students=2)
    left = allocate(org.id, room.ids["section"], since="2026-07-01", until="2026-11-02")
    later = allocate(org.id, room.ids["section"], since="2026-11-04")
    c = room.new_class()
    s = room.open(c["id"])
    assert (s["status"], s["opened_by"], s["scheduled_class_id"], s["closed_at"]) == (
        "open",
        room.instructor_id,
        c["id"],
        None,
    )
    assert s["marking_deadline"] == "2026-11-04T10:00:00+00:00"  # the end plus 24 hours
    assert s["counts"] == {"eligible": 2, "unmarked": 2, "present": 0, "absent": 0, "late": 0, "excused": 0}
    records = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))
    assert {r["student_id"] for r in records["items"]} == set(room.students)
    assert left not in {r["student_id"] for r in records["items"]} and later not in {
        r["student_id"] for r in records["items"]
    }
    assert all(r["id"] is None and r["status"] is None for r in records["items"])
    assert [r["student_name"] for r in records["items"]] == ["Student 0", "Student 1"]
    [event] = outbox("timetable-attendance.attendance-session.opened", org.id)
    assert (event["eligible_count"], event["scheduled_class_id"]) == (2, c["id"])
    assert ok(client.get(f"{BASE}/scheduled-classes/{c['id']}", headers=room.admin))["attendance_session"] == {
        "id": s["id"],
        "status": "open",
    }
    assert ok(client.get(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=room.faculty)) == s


def test_opening_twice_returns_the_open_session_with_200(client, room):
    c = room.new_class()
    first = room.open(c["id"])
    assert room.open(c["id"], status=200) == first
    assert len(outbox("timetable-attendance.attendance-session.opened", room.org.id)) == 1


def test_only_the_instructor_or_an_override_holder_opens(client, room):
    c = room.new_class()
    _, other_faculty = room.org.user(FACULTY)
    assert (
        err(client.post(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=other_faculty), 403)["code"]
        == "forbidden"
    )
    _, head = room.org.user(HEAD)  # no open key at all
    assert client.post(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=head).status_code == 403
    assert room.open(c["id"], headers=room.admin)["opened_by"] == room.admin_id


def test_opening_outside_the_marking_window_is_409_unless_override(client, room):
    early = room.new_class("2026-11-03T09:30:00+00:00")  # opens at 09:15
    late = room.new_class("2026-11-01T09:00:00+00:00")  # closed at 2026-11-02 10:00
    for c in (early, late):
        detail = err(client.post(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=room.faculty), 409)
        assert detail["code"] == "outside_marking_window" and detail["details"]["opens_at"]
    assert room.open(late["id"], headers=room.admin)["status"] == "open"


def test_marking_sets_the_listed_students_and_leaves_the_others(client, room):
    c = room.new_class()
    s = room.open(c["id"])
    a, b, _ = room.students
    marked = room.mark(s["id"], {a: "present", b: "late"})
    by_student = {r["student_id"]: r for r in marked["items"]}
    assert (by_student[a]["status"], by_student[a]["marked_by"], by_student[a]["marked_at"]) == (
        "present",
        room.instructor_id,
        "2026-11-03T09:00:00+00:00",
    )
    assert by_student[a]["id"] and by_student[b]["status"] == "late" and marked["total"] == 3
    again = room.mark(s["id"], {a: "absent"})
    assert {r["student_id"]: r["status"] for r in again["items"]}[b] == "late"
    late_only = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records?status=late", headers=room.faculty))
    assert [r["student_id"] for r in late_only["items"]] == [b]
    events = outbox("timetable-attendance.attendance-record.marked", room.org.id)
    assert [[r["status"] for r in e["records"]] for e in events] == [["present", "late"], ["absent"]]
    assert ok(client.get(f"{BASE}/attendance-sessions/{s['id']}", headers=room.faculty))["counts"] == {
        "eligible": 3,
        "unmarked": 1,
        "present": 0,
        "absent": 1,
        "late": 1,
        "excused": 0,
    }


def test_marking_refuses_ineligible_students_and_bad_input(client, room):
    c = room.new_class()
    s = room.open(c["id"])
    stranger = str(uuid.uuid4())
    detail = err(
        client.put(
            f"{BASE}/attendance-sessions/{s['id']}/records",
            json={"records": [{"student_id": stranger, "status": "present"}]},
            headers=room.faculty,
        ),
        422,
    )
    assert (detail["code"], detail["details"]["student_ids"]) == ("student_not_eligible", [stranger])
    url = f"{BASE}/attendance-sessions/{s['id']}/records"
    assert err(client.put(url, json={"records": []}, headers=room.faculty), 400)["code"] == "no_records"
    assert err(client.put(url, json={}, headers=room.faculty), 400)["code"] == "missing_field"
    bad = {"records": [{"student_id": room.students[0], "status": "here"}]}
    assert err(client.put(url, json=bad, headers=room.faculty), 400)["code"] == "invalid_choice"
    _, other = room.org.user(FACULTY)
    ok_body = {"records": [{"student_id": room.students[0], "status": "present"}]}
    assert client.put(url, json=ok_body, headers=other).status_code == 403
    assert not outbox("timetable-attendance.attendance-record.marked", room.org.id)


def test_closing_makes_the_unmarked_absent_and_completes_the_class(client, room):
    c = room.new_class()
    s = room.open(c["id"])
    a, b, z = room.students
    room.mark(s["id"], {a: "present", b: "excused"})
    closed = room.close(s["id"])
    assert (closed["status"], closed["closed_by"], closed["closed_at"]) == (
        "closed",
        room.instructor_id,
        "2026-11-03T09:00:00+00:00",
    )
    assert closed["counts"] == {"eligible": 3, "unmarked": 0, "present": 1, "absent": 1, "late": 0, "excused": 1}
    assert ok(client.get(f"{BASE}/scheduled-classes/{c['id']}", headers=room.admin))["status"] == "completed"
    [event] = outbox("timetable-attendance.attendance-session.closed", room.org.id)
    assert (event["present"], event["absent"], event["excused"], event["closed_by"]) == (1, 1, 1, room.instructor_id)
    assert err(client.post(f"{BASE}/attendance-sessions/{s['id']}/close", headers=room.faculty), 409)["code"] == (
        "session_closed"
    )
    url = f"{BASE}/attendance-sessions/{s['id']}/records"
    body = {"records": [{"student_id": z, "status": "present"}]}
    assert err(client.put(url, json=body, headers=room.faculty), 409)["code"] == "session_closed"
    assert {"attendance-session.opened", "attendance-record.marked", "attendance-session.closed"} <= {
        e.action for e in audit_entries(room.org.id, s["id"])
    }


def test_marking_after_the_deadline_is_409_unless_override(client, room, frozen_clock, monkeypatch):
    from datetime import timedelta

    from eos_timetable_attendance.application import service

    c = room.new_class()
    s = room.open(c["id"])
    monkeypatch.setattr(service, "clock", lambda: frozen_clock + timedelta(days=2))
    url = f"{BASE}/attendance-sessions/{s['id']}/records"
    body = {"records": [{"student_id": room.students[0], "status": "present"}]}
    assert err(client.put(url, json=body, headers=room.faculty), 409)["code"] == "marking_window_ended"
    assert ok(client.put(url, json=body, headers=room.admin))["total"] == 3


def test_correction_needs_a_reason_keeps_the_history_and_flags_the_record(client, room):
    c, s = room.held({room.students[0]: "absent"})
    records = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))["items"]
    record = next(r for r in records if r["student_id"] == room.students[0])
    url = f"{BASE}/attendance-records/{record['id']}"
    assert err(client.patch(url, json={"status": "present"}, headers=room.faculty), 400)["code"] == "invalid_text"
    body = {"status": "present", "reason": "came late with a pass", "remark": "pass 14"}
    corrected = ok(client.patch(url, json=body, headers=room.faculty))
    assert (corrected["status"], corrected["remark"], corrected["corrected"]) == ("present", "pass 14", True)
    history = ok(client.get(f"{url}/history", headers=room.faculty))
    assert history["attendance_record_id"] == record["id"]
    [change] = history["items"]
    assert (change["from_status"], change["to_status"], change["reason"], change["changed_by"]) == (
        "absent",
        "present",
        "came late with a pass",
        room.instructor_id,
    )
    [event] = outbox("timetable-attendance.attendance-record.updated", room.org.id)
    assert (event["from_status"], event["to_status"], event["student_id"]) == ("absent", "present", room.students[0])
    [entry] = audit_entries(room.org.id, record["id"])
    assert (entry.before, entry.after, entry.reason) == ({"status": "absent"}, {"status": "present"}, body["reason"])
    same = client.patch(url, json={"status": "present", "reason": "again"}, headers=room.faculty)
    assert err(same, 400)["code"] == "status_unchanged"


def test_a_record_of_an_open_session_is_marked_not_corrected(client, room):
    c = room.new_class()
    s = room.open(c["id"])
    marked = room.mark(s["id"], {room.students[0]: "present"})
    record = next(r for r in marked["items"] if r["student_id"] == room.students[0])
    r = client.patch(
        f"{BASE}/attendance-records/{record['id']}", json={"status": "late", "reason": "x"}, headers=room.faculty
    )
    assert err(r, 409)["code"] == "session_open"


def test_the_instructor_corrects_within_the_window_and_override_any_time(client, room, frozen_clock, monkeypatch):
    from datetime import timedelta

    from eos_timetable_attendance.application import service

    _, s = room.held({room.students[0]: "absent"})
    record = next(
        r
        for r in ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))["items"]
        if r["student_id"] == room.students[0]
    )
    monkeypatch.setattr(service, "clock", lambda: frozen_clock + timedelta(days=8))
    url = f"{BASE}/attendance-records/{record['id']}"
    body = {"status": "excused", "reason": "medical note"}
    assert err(client.patch(url, json=body, headers=room.faculty), 409)["code"] == "correction_window_passed"
    _, head = room.org.user(HEAD)  # correct-department grants nothing until PRD Q9
    assert err(client.patch(url, json=body, headers=head), 403)["code"] == "forbidden"
    assert ok(client.patch(url, json=body, headers=room.admin))["status"] == "excused"


def test_reads_are_limited_to_the_instructor_and_read_all_holders(client, room):
    _, s = room.held({room.students[0]: "absent"})
    record = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))["items"][0]
    _, other = room.org.user(FACULTY)
    _, head = room.org.user(HEAD)
    _, viewer = room.org.user(VIEWER)
    for url in (
        f"{BASE}/attendance-sessions/{s['id']}",
        f"{BASE}/attendance-sessions/{s['id']}/records",
        f"{BASE}/scheduled-classes/{s['scheduled_class_id']}/attendance-session",
        f"{BASE}/attendance-records/{record['id']}/history",
    ):
        assert client.get(url, headers=other).status_code == 403, url
        assert client.get(url, headers=head).status_code == 403, url
        assert client.get(url, headers=viewer).status_code == 200, url
        assert client.get(url, headers=room.admin).status_code == 200, url


def test_unknown_ids_are_404_with_their_codes(client, org):
    _, h = org.user(ADMIN)
    missing = str(uuid.uuid4())
    room = Classroom(client, org, students=0)
    c = room.new_class()
    cases = [
        (
            client.get(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=h),
            "attendance_session_not_found",
        ),
        (client.post(f"{BASE}/scheduled-classes/{missing}/attendance-session", headers=h), "scheduled_class_not_found"),
        (client.get(f"{BASE}/attendance-sessions/{missing}", headers=h), "attendance_session_not_found"),
        (client.post(f"{BASE}/attendance-sessions/{missing}/close", headers=h), "attendance_session_not_found"),
        (client.get(f"{BASE}/attendance-sessions/{missing}/records", headers=h), "attendance_session_not_found"),
        (client.get(f"{BASE}/attendance-records/{missing}/history", headers=h), "attendance_record_not_found"),
        (
            client.patch(f"{BASE}/attendance-records/{missing}", json={"status": "late", "reason": "x"}, headers=h),
            "attendance_record_not_found",
        ),
    ]
    for response, code in cases:
        assert err(response, 404)["code"] == code


def test_attendance_to_mark_lists_started_classes_still_open_for_marking(client, room, frozen_clock, monkeypatch):
    from datetime import timedelta

    from eos_timetable_attendance.application import service

    yesterday = room.new_class("2026-11-02T10:00:00+00:00")  # deadline 2026-11-03 11:00
    now = room.new_class("2026-11-03T08:30:00+00:00")
    room.new_class("2026-11-03T11:00:00+00:00")  # not started
    room.new_class("2026-11-01T09:00:00+00:00")  # window ended
    done, _ = room.held({}, "2026-11-03T09:00:00+00:00")  # closed
    cancelled = room.new_class("2026-11-03T07:00:00+00:00")
    ok(client.post(f"{BASE}/scheduled-classes/{cancelled['id']}/cancel", headers=room.admin))
    s = room.open(now["id"])
    room.mark(s["id"], {room.students[0]: "present"})
    _, someone = room.org.user(FACULTY)
    listed = ok(client.get(f"{BASE}/me/attendance-to-mark", headers=room.faculty))
    assert [i["scheduled_class"]["id"] for i in listed["items"]] == [yesterday["id"], now["id"]]
    assert listed["total"] == 2
    first, second = listed["items"]
    assert (first["marking_deadline"], "counts" in first) == ("2026-11-03T11:00:00+00:00", False)
    assert second["counts"]["present"] == 1 and second["scheduled_class"]["attendance_session"]["status"] == "open"
    assert done["id"] not in {i["scheduled_class"]["id"] for i in listed["items"]}
    assert ok(client.get(f"{BASE}/me/attendance-to-mark", headers=someone)) == {"items": [], "total": 0}
    monkeypatch.setattr(service, "clock", lambda: frozen_clock + timedelta(hours=3))
    later = ok(client.get(f"{BASE}/me/attendance-to-mark", headers=room.faculty))
    assert yesterday["id"] not in {i["scheduled_class"]["id"] for i in later["items"]}


def test_teaching_schedule_lists_the_callers_classes_on_a_date(client, room):
    _, other = room.org.user(FACULTY)
    a = room.new_class("2026-11-03T11:00:00+00:00")
    b = room.new_class("2026-11-03T08:00:00+00:00")
    tomorrow = room.new_class("2026-11-04T08:00:00+00:00")
    today = ok(client.get(f"{BASE}/me/teaching-schedule", headers=room.faculty))
    assert (today["date"], [c["id"] for c in today["items"]]) == ("2026-11-03", [b["id"], a["id"]])
    on = ok(client.get(f"{BASE}/me/teaching-schedule?date=2026-11-04", headers=room.faculty))
    assert [c["id"] for c in on["items"]] == [tomorrow["id"]]
    assert ok(client.get(f"{BASE}/me/teaching-schedule", headers=other))["items"] == []
    assert err(client.get(f"{BASE}/me/teaching-schedule?date=tomorrow", headers=room.faculty), 400)["code"] == (
        "invalid_date"
    )


def test_my_schedule_lists_the_classes_of_the_callers_sections(client, org):
    from conftest import STUDENT

    room = Classroom(client, org, students=0)
    student_id, h = org.user(STUDENT)
    allocate(org.id, room.ids["section"], student_id, since="2026-11-03")
    c = room.new_class("2026-11-03T10:00:00+00:00")
    room.new_class("2026-11-02T10:00:00+00:00")  # before the allocation
    cancelled = room.new_class("2026-11-03T12:00:00+00:00")
    ok(client.post(f"{BASE}/scheduled-classes/{cancelled['id']}/cancel", headers=room.admin))
    mine = ok(client.get(f"{BASE}/me/schedule", headers=h))
    assert [(x["id"], x["status"]) for x in mine["items"]] == [(c["id"], "scheduled"), (cancelled["id"], "cancelled")]
    assert ok(client.get(f"{BASE}/me/schedule?date=2026-11-02", headers=h))["items"] == []
    _, nobody = org.user(STUDENT)
    assert ok(client.get(f"{BASE}/me/schedule", headers=nobody)) == {"date": "2026-11-03", "items": []}
    assert client.get(f"{BASE}/me/schedule", headers=room.faculty).status_code == 403
