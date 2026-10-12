"""Integration tests through the HTTP API, against a throwaway SQLite database (see conftest)."""

from conftest import BASE, at
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_facility_booking.application.jobs import run_sweeps
from sqlalchemy import select

MANAGER = "facility-booking-manager"
APPROVER = "facility-booking-approver"
USER = "facility-booking-user"


def make_resource(client, headers, *, type_name="Room", **fields) -> dict:
    t = client.post(f"{BASE}/resource-types", json={"name": type_name}, headers=headers)
    assert t.status_code == 201, t.text
    body = {"name": "Room 1", "type_id": t.json()["id"], "capacity": 4} | fields
    r = client.post(f"{BASE}/resources", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def book(client, headers, resource_id, start, end, **extra):
    return client.post(
        f"{BASE}/bookings", json={"resource_id": resource_id, "start_at": start, "end_at": end} | extra, headers=headers
    )


def event_names(org_id: str) -> list[str]:
    with SessionLocal() as db:
        return [e.name for e in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org_id))]


def test_needs_a_token_and_a_permission(client, org):
    assert client.get(f"{BASE}/resources").status_code == 401
    _, nobody = org.user("some-other-role")
    assert client.get(f"{BASE}/resources", headers=nobody).status_code == 403


def test_book_a_free_resource(client, org):
    _, mgr = org.user(MANAGER)
    me, user = org.user(USER)
    room = make_resource(client, mgr)
    assert room["status"] == "active"
    assert room["effective_rules"]["slot_minutes"] == 30
    r = book(client, user, room["id"], at(9), at(10), title="Group practice")
    assert r.status_code == 201, r.text
    booking = r.json()["booking"]
    assert booking["status"] == "confirmed"
    assert booking["booked_for"] == me
    assert set(booking["can"]) >= {"edit", "cancel"}
    assert "facility-booking.booking.confirmed" in event_names(org.id)
    assert "facility-booking.resource.created" in event_names(org.id)


def test_double_booking_is_refused_and_hides_who_holds_the_slot(client, org):
    _, mgr = org.user(MANAGER)
    _, alice = org.user(USER)
    _, bob = org.user(USER)
    room = make_resource(client, mgr)
    assert book(client, alice, room["id"], at(9), at(10)).status_code == 201
    clash = book(client, bob, room["id"], at(9, 30), at(10, 30))
    assert clash.status_code == 409
    detail = clash.json()["detail"]
    assert detail["code"] == "booking_conflict"
    assert "booking_id" not in detail["conflicts"][0]
    as_manager = book(client, mgr, room["id"], at(9, 30), at(10, 30))
    assert "booking_id" in as_manager.json()["detail"]["conflicts"][0]


def test_rule_violations_return_422_with_codes(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    room = make_resource(client, mgr, rules={"max_duration_minutes": 60})
    client.put(
        f"{BASE}/resources/{room['id']}/opening-hours",
        json=[{"weekday": 1, "opens": "09:00", "closes": "17:00"}],
        headers=mgr,
    )
    client.post(
        f"{BASE}/resources/{room['id']}/blackouts",
        json={"start_at": at(14), "end_at": at(15), "reason": "Exam"},
        headers=mgr,
    )
    cases = {
        (at(9, 10), at(9, 40)): "misaligned_slot",
        (at(9), at(11)): "too_long",
        (at(17), at(17, 30)): "outside_opening_hours",
        (at(14), at(14, 30)): "in_blackout",
        (at(7), at(7, 30)): "in_the_past",
    }
    for (start, end), code in cases.items():
        r = book(client, user, room["id"], start, end)
        assert r.status_code == 422, (code, r.text)
        assert r.json()["detail"]["code"] == code


def test_approval_flow(client, org):
    _, mgr = org.user(MANAGER)
    approver_id, approver = org.user(APPROVER)
    _, stranger = org.user(APPROVER)
    _, user = org.user(USER)
    room = make_resource(client, mgr, rules={"requires_approval": True}, approver_user_ids=[approver_id])
    booking = book(client, user, room["id"], at(9), at(10)).json()["booking"]
    assert booking["status"] == "pending"
    assert book(client, user, room["id"], at(9), at(10)).status_code == 409  # pending holds the slot
    assert client.post(f"{BASE}/bookings/{booking['id']}/approve", headers=stranger).status_code == 404
    queue = client.get(f"{BASE}/bookings", params={"scope": "managed", "status": "pending"}, headers=approver).json()
    assert [b["id"] for b in queue["items"]] == [booking["id"]]
    assert set(queue["items"][0]["can"]) >= {"approve", "reject"}
    ok = client.post(f"{BASE}/bookings/{booking['id']}/approve", json={"note": "fine"}, headers=approver)
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"
    assert ok.json()["decided_by"] == approver_id
    again = client.post(f"{BASE}/bookings/{booking['id']}/reject", json={"reason": "late"}, headers=approver)
    assert again.status_code == 409


def test_reject_needs_reason(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    room = make_resource(client, mgr, rules={"requires_approval": True})
    booking = book(client, user, room["id"], at(9), at(10)).json()["booking"]
    assert client.post(f"{BASE}/bookings/{booking['id']}/reject", json={}, headers=mgr).status_code == 422
    r = client.post(f"{BASE}/bookings/{booking['id']}/reject", json={"reason": "Exam week"}, headers=mgr)
    assert r.json()["status"] == "rejected"
    assert "facility-booking.booking.rejected" in event_names(org.id)


def test_booking_for_someone_else_needs_manage(client, org):
    _, mgr = org.user(MANAGER)
    other_id, _ = org.user(USER)
    _, user = org.user(USER)
    room = make_resource(client, mgr)
    assert book(client, user, room["id"], at(9), at(10), booked_for=other_id).status_code == 403
    r = book(client, mgr, room["id"], at(9), at(10), booked_for=other_id)
    assert r.status_code == 201
    assert r.json()["booking"]["booked_for"] == other_id


def test_recurring_booking_and_series_cancel(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    _, rival = org.user(USER)
    room = make_resource(client, mgr)
    assert book(client, rival, room["id"], at(9, day=19), at(10, day=19)).status_code == 201
    weekly = {"frequency": "weekly", "count": 3}
    refused = book(client, user, room["id"], at(9), at(10), recurrence=weekly)
    assert refused.status_code == 409
    r = book(client, user, room["id"], at(9), at(10), recurrence=weekly, skip_conflicts=True)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["created"]) == 2
    assert len(body["skipped"]) == 1
    cancelled = client.post(f"{BASE}/series/{body['series_id']}/cancel", json={"reason": "term over"}, headers=user)
    assert cancelled.status_code == 200
    assert {b["status"] for b in cancelled.json()} == {"cancelled"}


def test_role_restricted_resource_and_capacity(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    _, senior = org.user(USER, "senior")
    room = make_resource(client, mgr, rules={"bookable_role_ids": ["senior"]}, capacity=2)
    assert book(client, user, room["id"], at(9), at(10)).status_code == 403
    assert book(client, senior, room["id"], at(9), at(10), party_size=3).json()["detail"]["code"] == "over_capacity"
    assert book(client, senior, room["id"], at(9), at(10), party_size=2).status_code == 201


def test_reschedule_and_cancel(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    _, other = org.user(USER)
    room = make_resource(client, mgr)
    booking = book(client, user, room["id"], at(9), at(10)).json()["booking"]
    moved = client.patch(f"{BASE}/bookings/{booking['id']}", json={"start_at": at(11), "end_at": at(12)}, headers=user)
    assert moved.status_code == 200, moved.text
    assert moved.json()["start_at"].startswith("2026-10-12T11:00")
    assert "facility-booking.booking.rescheduled" in event_names(org.id)
    assert client.post(f"{BASE}/bookings/{booking['id']}/cancel", headers=other).status_code == 404
    no_reason = client.post(f"{BASE}/bookings/{booking['id']}/cancel", json={}, headers=mgr)
    assert no_reason.status_code == 422
    done = client.post(f"{BASE}/bookings/{booking['id']}/cancel", json={"reason": "not needed"}, headers=user)
    assert done.json()["status"] == "cancelled"
    assert book(client, other, room["id"], at(11), at(12)).status_code == 201  # the slot is free again


def test_check_in_no_show_and_sweeps(client, org, monkeypatch):
    from eos_facility_booking.application import service

    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    room = make_resource(client, mgr, rules={"check_in_required": True})
    early = book(client, user, room["id"], at(9), at(10)).json()["booking"]
    late = book(client, user, room["id"], at(11), at(12)).json()["booking"]
    assert client.post(f"{BASE}/bookings/{early['id']}/check-in", headers=user).status_code == 409  # too early
    from datetime import UTC, datetime

    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 12, 9, 5, tzinfo=UTC))
    checked = client.post(f"{BASE}/bookings/{early['id']}/check-in", headers=user)
    assert checked.status_code == 200
    assert checked.json()["status"] == "checked_in"
    with SessionLocal() as db:
        counts = run_sweeps(db, now=datetime(2026, 10, 12, 12, 30, tzinfo=UTC))
    assert counts["completed"] >= 1
    assert counts["no_show"] >= 1
    assert client.get(f"{BASE}/bookings/{early['id']}", headers=user).json()["status"] == "completed"
    assert client.get(f"{BASE}/bookings/{late['id']}", headers=user).json()["status"] == "no_show"
    assert "facility-booking.booking.no-show-recorded" in event_names(org.id)


def test_out_of_service_blocks_bookings_and_lists_affected(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    room = make_resource(client, mgr)
    booking = book(client, user, room["id"], at(9), at(10)).json()["booking"]
    r = client.put(
        f"{BASE}/resources/{room['id']}/status", json={"status": "under_maintenance", "reason": "leak"}, headers=mgr
    )
    assert r.status_code == 200
    assert [b["id"] for b in r.json()["affected_bookings"]] == [booking["id"]]
    assert (
        client.get(f"{BASE}/bookings/{booking['id']}", headers=user).json()["status"] == "confirmed"
    )  # not silently cancelled
    blocked = book(client, user, room["id"], at(11), at(12))
    assert blocked.json()["detail"]["code"] == "resource_not_active"


def test_availability_hides_holder_from_users(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    room = make_resource(client, mgr)
    client.put(
        f"{BASE}/resources/{room['id']}/opening-hours",
        json=[{"weekday": 1, "opens": "09:00", "closes": "17:00"}],
        headers=mgr,
    )
    book(client, user, room["id"], at(10), at(11), title="Secret")
    params = {"from": at(0), "to": at(0, day=13)}
    seen = client.get(f"{BASE}/resources/{room['id']}/availability", params=params, headers=user).json()
    kinds = [b["kind"] for b in seen["busy"]]
    assert kinds.count("closed") == 2 and kinds.count("booking") == 1
    assert "title" not in next(b for b in seen["busy"] if b["kind"] == "booking")
    assert [(f["start_at"][11:16], f["end_at"][11:16]) for f in seen["free"]] == [
        ("09:00", "10:00"),
        ("11:00", "17:00"),
    ]
    staff = client.get(f"{BASE}/resources/{room['id']}/availability", params=params, headers=mgr).json()
    assert next(b for b in staff["busy"] if b["kind"] == "booking")["title"] == "Secret"


def test_widget_queries_and_summary(client, org):
    _, mgr = org.user(MANAGER)
    me, user = org.user(USER)
    approver_id, approver = org.user(APPROVER)
    open_room = make_resource(client, mgr, type_name="Open", name="Open room")
    gated = make_resource(
        client,
        mgr,
        type_name="Gated",
        name="Gated room",
        rules={"requires_approval": True},
        approver_user_ids=[approver_id],
    )
    book(client, user, open_room["id"], at(9), at(10))
    book(client, user, gated["id"], at(13), at(14))
    book(client, user, open_room["id"], at(9, day=14), at(10, day=14))
    mine = client.get(f"{BASE}/bookings", params={"scope": "mine", "from": "now"}, headers=user).json()
    assert mine["total"] == 3
    assert all(me in (b["booked_by"], b["booked_for"]) for b in mine["items"])
    today = client.get(f"{BASE}/bookings", params={"scope": "managed", "date": "today"}, headers=mgr).json()
    assert today["total"] == 2
    approvers_view = client.get(f"{BASE}/bookings", params={"scope": "managed", "from": "now"}, headers=approver).json()
    assert [b["resource_id"] for b in approvers_view["items"]] == [gated["id"]]
    summary = client.get(f"{BASE}/summary", headers=mgr).json()
    assert summary["date"] == "2026-10-12"
    assert summary["bookings_today"] == 2
    assert summary["pending_approval"] == 1


def test_resource_search_and_free_filter(client, org):
    _, mgr = org.user(MANAGER)
    _, user = org.user(USER)
    a = make_resource(client, mgr, type_name="Search", name="North studio", attributes={"projector": "yes"}, code="N1")
    make_resource(client, mgr, type_name="Search 2", name="South studio", capacity=10)
    assert [
        r["id"] for r in client.get(f"{BASE}/resources", params={"q": "projector"}, headers=user).json()["items"]
    ] == [a["id"]]
    assert client.get(f"{BASE}/resources", params={"min_capacity": 8}, headers=user).json()["total"] == 1
    book(client, user, a["id"], at(9), at(10))
    free = client.get(f"{BASE}/resources", params={"free_from": at(9), "free_to": at(10)}, headers=user).json()
    assert a["id"] not in [r["id"] for r in free["items"]]
    dup = client.post(f"{BASE}/resources", json={"name": "Copy", "type_id": a["type_id"], "code": "N1"}, headers=mgr)
    assert dup.status_code == 409
