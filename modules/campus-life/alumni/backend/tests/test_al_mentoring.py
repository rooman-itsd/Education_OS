"""Mentoring assignments and sessions: who can be assigned, the date rules (A7), ending, and the session lifecycle."""

from datetime import UTC, datetime, timedelta

import pytest
from al_support import (
    BASE,
    NOW,
    TODAY,
    add_alumnus,
    assign,
    assigned,
    code,
    iso,
    mentor,
    outbox,
    schedule,
    scheduled,
    session_body,
)


def test_assign_a_mentor(client, org):
    m = mentor(client, org)
    r = assign(client, org, m, focus="Finance careers")
    assert r.status_code == 201, r.text
    x = r.json()
    assert x["status"] == "active" and x["organisation_id"] == org.id
    assert x["mentor_id"] == m["id"] and x["student_id"] == org.ids["student"] and x["student_name"] == "Riya Sharma"
    assert x["started_on"] == TODAY and x["focus"] == "Finance careers" and x["assigned_by"] == org.ids["coord"]
    assert x["ended_on"] is None and x["end_reason"] is None and x["next_session_at"] is None
    assert x["mentor"]["email"] == m["email"] and x["mentor"]["phone"] == m["phone"]
    assert "notes" not in x["mentor"]
    assert client.get(f"{BASE}/mentoring/assignments/{x['id']}", headers=org.coord).json() == x
    assert outbox("alumni.mentoring-assignment.started", org.id) == [
        {
            "organisation_id": org.id,
            "assignment_id": x["id"],
            "mentor_id": m["id"],
            "student_id": org.ids["student"],
            "started_on": TODAY,
        }
    ]


def test_student_id_is_stored_in_its_canonical_form(client, org):
    m = mentor(client, org)
    r = client.post(
        f"{BASE}/mentoring/assignments",
        json={"mentor_id": m["id"], "student_id": org.ids["student"].upper()},
        headers=org.coord,
    )
    assert r.status_code == 201 and r.json()["student_id"] == org.ids["student"]
    bad = client.post(
        f"{BASE}/mentoring/assignments", json={"mentor_id": m["id"], "student_id": "not-a-uuid"}, headers=org.coord
    )
    assert bad.status_code == 422


def test_start_date_is_today_or_earlier(client, org):
    m = mentor(client, org)
    past = assigned(client, org, m, started_on="2026-08-01")
    assert past["started_on"] == "2026-08-01"
    r = assign(client, org, m, student="student2", started_on="2026-11-04")
    assert r.status_code == 422 and code(r) == "invalid_date" and r.json()["detail"]["field"] == "started_on"


def test_today_is_the_asia_kolkata_date(client, org, clock):
    m = mentor(client, org)
    clock.now = datetime(2026, 11, 3, 18, 45, tzinfo=UTC)  # 00:15 on 4 November in India
    x = assigned(client, org, m, started_on="2026-11-04")
    assert x["started_on"] == "2026-11-04"
    clock.now = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)  # 23:30 on 3 November in India
    r = assign(client, org, m, student="student2", started_on="2026-11-04")
    assert r.status_code == 422 and code(r) == "invalid_date"
    default = assigned(client, org, m, student="student2")
    assert default["started_on"] == "2026-11-03"


def test_who_can_be_assigned(client, org, other_org):
    plain = add_alumnus(client, org)
    r = assign(client, org, plain)
    assert r.status_code == 409 and code(r) == "not_a_mentor"
    gone = mentor(client, org)
    client.post(f"{BASE}/directory/{gone['id']}/archive", headers=org.coord)
    r = assign(client, org, gone)
    assert r.status_code == 409 and code(r) == "alumnus_archived"
    r = client.post(
        f"{BASE}/mentoring/assignments",
        json={"mentor_id": "missing", "student_id": org.ids["student"]},
        headers=org.coord,
    )
    assert r.status_code == 404 and code(r) == "not_found"
    foreign = mentor(client, other_org)
    r = assign(client, org, foreign)
    assert r.status_code == 404 and code(r) == "not_found"
    assert outbox("alumni.mentoring-assignment.started", org.id) == []


def test_one_active_mentor_per_student_and_several_mentees_per_mentor(client, org):
    m = mentor(client, org)
    other = mentor(client, org, full_name="Second Mentor")
    x = assigned(client, org, m)
    r = assign(client, org, other)
    assert r.status_code == 409 and code(r) == "student_already_assigned"
    assigned(client, org, m, student="student2")
    assert client.get(f"{BASE}/directory/{m['id']}", headers=org.coord).json()["active_mentees"] == 2
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    again = assign(client, org, other)
    assert again.status_code == 201  # once the first assignment ended


def test_the_partial_unique_index_holds_one_active_assignment_per_student(client, org):
    """The database itself refuses a second active assignment for the same (organisation, student)."""
    from eos_alumni.infrastructure.models import Assignment
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope
    from sqlalchemy.exc import IntegrityError

    m = mentor(client, org)
    assigned(client, org, m)
    with SessionLocal() as db, organisation_scope(org.id):
        db.add(
            Assignment(
                organisation_id=org.id,
                mentor_id=m["id"],
                student_id=org.ids["student"],
                started_on=NOW.date(),
                status="active",
                assigned_by=org.ids["coord"],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_list_assignments_active_first_then_newest_with_filters(client, org, clock):
    m1 = mentor(client, org, full_name="M1")
    m2 = mentor(client, org, full_name="M2")
    ended = assigned(client, org, m1, student="student")
    client.post(f"{BASE}/mentoring/assignments/{ended['id']}/end", headers=org.coord)
    clock.advance(minutes=1)
    a1 = assigned(client, org, m1, student="student2")
    clock.advance(minutes=1)
    a2 = assigned(client, org, m2, student="student")

    def ids(**params):
        r = client.get(f"{BASE}/mentoring/assignments", params=params, headers=org.coord)
        assert r.status_code == 200, r.text
        return [x["id"] for x in r.json()["items"]]

    assert ids() == [a2["id"], a1["id"], ended["id"]]
    assert ids(status="active") == [a2["id"], a1["id"]]
    assert ids(status="ended") == [ended["id"]]
    assert ids(mentor_id=m1["id"]) == [a1["id"], ended["id"]]
    assert ids(student_id=org.ids["student"]) == [a2["id"], ended["id"]]
    page = client.get(f"{BASE}/mentoring/assignments", params={"limit": 2}, headers=org.coord).json()
    assert len(page["items"]) == 2 and page["next_cursor"] == "2"
    rest = client.get(f"{BASE}/mentoring/assignments", params={"cursor": "2"}, headers=org.coord).json()
    assert [x["id"] for x in rest["items"]] == [ended["id"]] and rest["next_cursor"] is None
    r = client.get(f"{BASE}/mentoring/assignments", params={"cursor": "x"}, headers=org.coord)
    assert r.status_code == 400 and code(r) == "invalid_cursor"
    assert client.get(f"{BASE}/mentoring/assignments", params={"status": "x"}, headers=org.coord).status_code == 422


def test_end_an_assignment_cancels_its_scheduled_sessions(client, org, clock):
    x = assigned(client, org, started_on="2026-10-01")
    s1 = scheduled(client, org, x, NOW + timedelta(days=2))
    s2 = scheduled(client, org, x, NOW + timedelta(days=9))
    done = scheduled(client, org, x, NOW - timedelta(days=3))
    client.post(f"{BASE}/mentoring/sessions/{done['id']}/complete", headers=org.coord)
    r = client.post(
        f"{BASE}/mentoring/assignments/{x['id']}/end",
        json={"ended_on": "2026-11-02", "reason": "Student graduated"},
        headers=org.coord,
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["status"] == "ended" and got["ended_on"] == "2026-11-02" and got["end_reason"] == "Student graduated"
    assert got["next_session_at"] is None
    sessions = {
        s["id"]: s for s in client.get(f"{BASE}/mentoring/assignments/{x['id']}/sessions", headers=org.coord).json()
    }
    assert sessions[s1["id"]]["status"] == sessions[s2["id"]]["status"] == "cancelled"
    assert sessions[s1["id"]]["cancel_reason"] == "The assignment ended."
    assert sessions[done["id"]]["status"] == "completed"
    assert outbox("alumni.mentoring-assignment.ended", org.id) == [
        {
            "organisation_id": org.id,
            "assignment_id": x["id"],
            "mentor_id": x["mentor_id"],
            "student_id": x["student_id"],
            "ended_on": "2026-11-02",
        }
    ]
    cancelled = outbox("alumni.mentoring-session.cancelled", org.id)
    assert {c["session_id"] for c in cancelled} == {s1["id"], s2["id"]}
    again = client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    assert again.status_code == 409 and code(again) == "assignment_not_active"
    late = schedule(client, org, x, NOW + timedelta(days=1))
    assert late.status_code == 409 and code(late) == "assignment_not_active"


def test_end_date_is_between_start_and_today(client, org):
    x = assigned(client, org, started_on="2026-10-10")
    for bad in ("2026-10-09", "2026-11-04"):
        r = client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", json={"ended_on": bad}, headers=org.coord)
        assert r.status_code == 422 and code(r) == "invalid_date" and r.json()["detail"]["field"] == "ended_on"
    same_day = client.post(
        f"{BASE}/mentoring/assignments/{x['id']}/end", json={"ended_on": "2026-10-10"}, headers=org.coord
    )
    assert same_day.status_code == 200 and same_day.json()["ended_on"] == "2026-10-10"


def test_end_defaults_to_today_without_a_body(client, org):
    x = assigned(client, org)
    r = client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    assert r.status_code == 200 and r.json()["ended_on"] == TODAY
    long = assigned(client, org, student="student2")
    r = client.post(f"{BASE}/mentoring/assignments/{long['id']}/end", json={"reason": "x" * 2001}, headers=org.coord)
    assert r.status_code == 422


def test_schedule_and_list_sessions(client, org):
    x = assigned(client, org)
    later = scheduled(client, org, x, NOW + timedelta(days=7), mode="in_person", location="Room 4")
    sooner = scheduled(client, org, x, NOW + timedelta(days=1))
    assert sooner["status"] == "scheduled" and sooner["assignment_id"] == x["id"]
    assert sooner["organisation_id"] == org.id and sooner["created_by"] == org.ids["coord"]
    assert sooner["scheduled_at"] == iso(NOW + timedelta(days=1)) and sooner["duration_minutes"] == 45
    assert sooner["notes"] is None and sooner["cancel_reason"] is None
    listed = client.get(f"{BASE}/mentoring/assignments/{x['id']}/sessions", headers=org.coord).json()
    assert [s["id"] for s in listed] == [sooner["id"], later["id"]]
    one = client.get(f"{BASE}/mentoring/assignments/{x['id']}/sessions", params={"limit": 1}, headers=org.coord)
    assert [s["id"] for s in one.json()] == [sooner["id"]]
    got = client.get(f"{BASE}/mentoring/assignments/{x['id']}", headers=org.coord).json()
    assert got["next_session_at"] == sooner["scheduled_at"]
    assert outbox("alumni.mentoring-session.scheduled", org.id)[0] == {
        "organisation_id": org.id,
        "session_id": later["id"],
        "assignment_id": x["id"],
        "student_id": x["student_id"],
        "scheduled_at": later["scheduled_at"],
        "mode": "in_person",
    }


def test_a_time_with_an_offset_is_stored_in_utc(client, org):
    x = assigned(client, org)
    s = scheduled(client, org, x, NOW, scheduled_at="2026-11-05T15:30:00+05:30")
    assert s["scheduled_at"] == "2026-11-05T10:00:00+00:00"


def test_session_values(client, org):
    x = assigned(client, org, started_on="2026-11-01")
    before = schedule(client, org, x, datetime(2026, 10, 31, 18, 0, tzinfo=UTC))  # 23:30 on 31 Oct in India
    assert before.status_code == 422 and code(before) == "invalid_scheduled_at"
    on_start = schedule(client, org, x, datetime(2026, 10, 31, 18, 30, tzinfo=UTC))  # 00:00 on 1 Nov in India
    assert on_start.status_code == 201
    for minutes in (0, 481):
        r = schedule(client, org, x, NOW, duration_minutes=minutes)
        assert r.status_code == 422 and code(r) == "invalid_duration"
    assert schedule(client, org, x, NOW, duration_minutes=None).status_code == 201
    assert schedule(client, org, x, NOW, mode="carrier-pigeon").status_code == 422
    assert schedule(client, org, x, NOW, location="x" * 501).status_code == 422
    assert schedule(client, org, x, NOW, topic="x" * 201).status_code == 422


def test_reschedule_publishes_only_when_the_time_moves(client, org):
    x = assigned(client, org)
    s = scheduled(client, org, x, NOW + timedelta(days=1))
    same = client.put(
        f"{BASE}/mentoring/sessions/{s['id']}",
        json=session_body(NOW + timedelta(days=1), topic="CV review"),
        headers=org.coord,
    )
    assert same.status_code == 200 and same.json()["topic"] == "CV review"
    assert outbox("alumni.mentoring-session.rescheduled", org.id) == []
    moved_to = NOW + timedelta(days=3, hours=2)
    body = {"scheduled_at": iso(moved_to), "mode": "phone"}  # a full replace: the rest is cleared
    moved = client.put(f"{BASE}/mentoring/sessions/{s['id']}", json=body, headers=org.coord)
    assert moved.status_code == 200, moved.text
    got = moved.json()
    assert got["scheduled_at"] == iso(moved_to) and got["mode"] == "phone"
    assert got["duration_minutes"] is None and got["location"] is None and got["topic"] is None
    assert outbox("alumni.mentoring-session.rescheduled", org.id) == [
        {
            "organisation_id": org.id,
            "session_id": s["id"],
            "assignment_id": x["id"],
            "student_id": x["student_id"],
            "scheduled_at": iso(moved_to),
        }
    ]
    bad = client.put(
        f"{BASE}/mentoring/sessions/{s['id']}", json=session_body(NOW, duration_minutes=999), headers=org.coord
    )
    assert bad.status_code == 422 and code(bad) == "invalid_duration"
    early = client.put(
        f"{BASE}/mentoring/sessions/{s['id']}", json=session_body(NOW - timedelta(days=30)), headers=org.coord
    )
    assert early.status_code == 422 and code(early) == "invalid_scheduled_at"


def test_complete_and_cancel_only_a_scheduled_session(client, org):
    x = assigned(client, org)
    s = scheduled(client, org, x, NOW + timedelta(days=1))
    r = client.post(
        f"{BASE}/mentoring/sessions/{s['id']}/complete", json={"notes": "STAFF-ONLY-SESSION-NOTE"}, headers=org.coord
    )
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert r.json()["notes"] == "STAFF-ONLY-SESSION-NOTE"
    for method, path, body in (
        ("post", f"/mentoring/sessions/{s['id']}/complete", None),
        ("post", f"/mentoring/sessions/{s['id']}/cancel", None),
        ("put", f"/mentoring/sessions/{s['id']}", session_body(NOW)),
    ):
        again = client.request(method.upper(), f"{BASE}{path}", json=body, headers=org.coord)
        assert again.status_code == 409 and code(again) == "session_not_scheduled", path
    c = scheduled(client, org, x, NOW + timedelta(days=2))
    r = client.post(
        f"{BASE}/mentoring/sessions/{c['id']}/cancel", json={"reason": "Mentor travelling"}, headers=org.coord
    )
    assert (
        r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["cancel_reason"] == "Mentor travelling"
    )
    assert client.post(f"{BASE}/mentoring/sessions/{c['id']}/complete", headers=org.coord).status_code == 409
    assert (
        client.post(
            f"{BASE}/mentoring/sessions/{c['id']}/complete", json={"notes": "x" * 2001}, headers=org.coord
        ).status_code
        == 422
    )
    assert outbox("alumni.mentoring-session.completed", org.id) == [
        {"organisation_id": org.id, "session_id": s["id"], "assignment_id": x["id"], "student_id": x["student_id"]}
    ]
    assert outbox("alumni.mentoring-session.cancelled", org.id) == [
        {"organisation_id": org.id, "session_id": c["id"], "assignment_id": x["id"], "student_id": x["student_id"]}
    ]
    plain = scheduled(client, org, x, NOW + timedelta(days=3))
    assert client.post(f"{BASE}/mentoring/sessions/{plain['id']}/complete", headers=org.coord).json()["notes"] is None


def test_missing_ids_are_404(client, org):
    for method, path, body in (
        ("get", "/mentoring/assignments/nope", None),
        ("post", "/mentoring/assignments/nope/end", None),
        ("get", "/mentoring/assignments/nope/sessions", None),
        ("post", "/mentoring/assignments/nope/sessions", session_body(NOW)),
        ("put", "/mentoring/sessions/nope", session_body(NOW)),
        ("post", "/mentoring/sessions/nope/complete", None),
        ("post", "/mentoring/sessions/nope/cancel", None),
    ):
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=org.coord)
        assert r.status_code == 404 and code(r) == "not_found", path


@pytest.mark.parametrize("who", ["student", "faculty", "nobody"])
def test_only_staff_use_mentoring(client, org, who):
    x = assigned(client, org)
    s = scheduled(client, org, x, NOW + timedelta(days=1))
    h = org.headers[who]
    for method, path, body in (
        ("get", "/mentoring/assignments", None),
        ("post", "/mentoring/assignments", {"mentor_id": x["mentor_id"], "student_id": org.ids["student2"]}),
        ("get", f"/mentoring/assignments/{x['id']}", None),
        ("post", f"/mentoring/assignments/{x['id']}/end", None),
        ("get", f"/mentoring/assignments/{x['id']}/sessions", None),
        ("post", f"/mentoring/assignments/{x['id']}/sessions", session_body(NOW)),
        ("put", f"/mentoring/sessions/{s['id']}", session_body(NOW)),
        ("post", f"/mentoring/sessions/{s['id']}/complete", None),
        ("post", f"/mentoring/sessions/{s['id']}/cancel", None),
    ):
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=h)
        assert r.status_code == 403 and code(r) == "forbidden", (who, path)
