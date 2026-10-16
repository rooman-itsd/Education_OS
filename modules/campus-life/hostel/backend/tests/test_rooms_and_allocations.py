"""Hostels, rooms and allocation (docs/user-stories.md HR-1..HR-7, AL-1..AL-11)."""

from datetime import UTC, datetime

from conftest import BASE, YEAR, events
from eos_hostel.application import service


def test_hostel_setup_and_occupancy(campus, client):
    c = campus
    h = c.hostel
    assert h["active"] is True and h["organisation_id"] == c.org.id
    assert c.post("/hostels", {"name": "No type"}, c.admin).status_code == 422
    r = client.patch(f"{BASE}/hostels/{h['id']}", json={"active": False}, headers=c.admin)
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["name"] == "North Block"
    assert [x["id"] for x in c.get("/hostels?active=true", c.viewer).json()] == []
    client.patch(f"{BASE}/hostels/{h['id']}", json={"active": True}, headers=c.admin)
    c.resident("1")
    detail = c.get(f"/hostels/{h['id']}", c.viewer).json()
    assert (detail["rooms"], detail["beds"], detail["beds_occupied"], detail["beds_confirmed"]) == (1, 2, 1, 0)
    assert c.get("/hostels/not-a-real-id", c.viewer).status_code == 404


def test_only_the_office_manages_hostels_and_rooms(campus):
    c = campus
    assert c.post("/hostels", {"name": "X", "occupancy_type": "men"}, c.warden).status_code == 403
    rooms = f"/hostels/{c.hostel['id']}/rooms"
    assert c.post(rooms, {"number": "9", "room_type": "single", "capacity": 1}, c.security).status_code == 403
    _, resident = c.org.user("hostel-resident")
    assert c.get("/hostels", resident).status_code == 403
    assert c.get("/hostels", {}).status_code == 401


def test_room_numbers_are_unique_per_hostel(campus):
    c = campus
    path = f"/hostels/{c.hostel['id']}/rooms"
    r = c.post(path, {"number": "101", "room_type": "single", "capacity": 1}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "room_exists"
    assert c.post(path, {"number": "102", "room_type": "single", "capacity": 0}, c.admin).status_code == 422


def test_capacity_cannot_drop_below_occupancy(campus, client):
    c = campus
    c.resident("1")
    c.resident("2")
    r = client.patch(f"{BASE}/rooms/{c.room['id']}", json={"capacity": 1}, headers=c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "capacity_below_occupancy"
    r = client.patch(f"{BASE}/rooms/{c.room['id']}", json={"capacity": 3, "room_type": "triple"}, headers=c.admin)
    assert r.status_code == 200 and r.json()["free_beds"] == ["3"] and r.json()["room_type"] == "triple"


def test_close_and_reopen_a_room(campus, client):
    c = campus
    path = f"{BASE}/rooms/{c.room['id']}"
    assert client.patch(path, json={"status": "closed"}, headers=c.admin).status_code == 422  # reason required
    r = client.patch(path, json={"status": "closed", "reason": "Plumbing"}, headers=c.admin)
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["free_beds"] == []
    assert events("hostel.room.closed", c.org.id)[-1]["reason"] == "Plumbing"
    person_id, _ = c.org.user("hostel-resident")
    body = {"person_id": person_id, "room_id": c.room["id"], "bed": "1", "academic_year": YEAR}
    r = c.post("/allocations", {**body, "from": "2026-10-12", "to": "2027-05-31"}, c.warden)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "room_closed"
    assert client.patch(path, json={"status": "open"}, headers=c.admin).json()["free_beds"] == ["1", "2"]
    assert events("hostel.room.reopened", c.org.id)[-1]["room_id"] == c.room["id"]


def test_find_free_beds(campus):
    c = campus
    full = c.post(f"/hostels/{c.hostel['id']}/rooms", {"number": "102", "room_type": "single", "capacity": 1}, c.admin)
    c.resident("1", room_id=full.json()["id"])
    rooms = c.get(f"/hostels/{c.hostel['id']}/rooms?has_free_bed=true", c.warden).json()
    assert [r["number"] for r in rooms] == ["101"]
    assert c.get(f"/hostels/{c.hostel['id']}/rooms?status=closed", c.warden).json() == []


def test_request_confirm_check_in_and_out(campus):
    c = campus
    person_id, me = c.org.user("hostel-resident")
    req = c.post("/me/room-requests", {"academic_year": YEAR, "preferred_room_type": "double"}, me)
    assert req.status_code == 201 and req.json()["status"] == "requested"
    assert events("hostel.allocation.requested", c.org.id)[-1]["person_id"] == person_id
    again = c.post("/me/room-requests", {"academic_year": YEAR}, me)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "already_requested"
    assert c.get("/me/allocation", me).json()["allocation"]["status"] == "requested"

    aid = req.json()["id"]
    r = c.post(f"/allocations/{aid}/confirm", {"room_id": c.room["id"], "bed": "2", "from": "2026-10-12"}, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["room_number"] == "101"
    ev = events("hostel.allocation.confirmed", c.org.id)[-1]
    assert ev["room_type"] == "double" and ev["academic_year"] == YEAR and ev["hostel_id"] == c.hostel["id"]
    assert c.post(f"/allocations/{aid}/confirm", {"room_id": c.room["id"], "bed": "1"}, c.warden).status_code == 409

    assert c.post(f"/allocations/{aid}/check-out", None, c.warden).status_code == 409  # not occupied yet
    r = c.post(f"/allocations/{aid}/check-in", None, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "occupied" and r.json()["checked_in_at"]
    assert events("hostel.allocation.occupied", c.org.id)[-1]["allocation_id"] == aid
    mine = c.get("/me/allocation", me).json()
    assert mine["allocation"]["id"] == aid and mine["hostel"]["id"] == c.hostel["id"]

    r = c.post(f"/allocations/{aid}/check-out", {"condition_notes": "Window cracked"}, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "vacated" and r.json()["condition_notes"] == "Window cracked"
    assert events("hostel.allocation.vacated", c.org.id)[-1]["allocation_id"] == aid
    assert "2" in c.get(f"/hostels/{c.hostel['id']}/rooms", c.warden).json()[0]["free_beds"]


def test_a_bed_holds_one_allocation_and_a_person_one_bed(campus):
    c = campus
    c.resident("1")
    person_id, _ = c.org.user("hostel-resident")
    body = {"room_id": c.room["id"], "academic_year": YEAR, "from": "2026-10-12", "to": "2027-05-31"}
    r = c.post("/allocations", {**body, "person_id": person_id, "bed": "1"}, c.warden)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bed_taken"
    r = c.post("/allocations", {**body, "person_id": person_id, "bed": "7"}, c.warden)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_bed"
    assert c.post("/allocations", {**body, "person_id": person_id, "bed": "2"}, c.warden).status_code == 201
    other = c.post(f"/hostels/{c.hostel['id']}/rooms", {"number": "103", "room_type": "single", "capacity": 1}, c.admin)
    r = c.post("/allocations", {**body, "room_id": other.json()["id"], "person_id": person_id, "bed": "1"}, c.warden)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "person_allocated"


def test_cancel_before_check_in(campus):
    c = campus
    person_id, me = c.org.user("hostel-resident")
    req = c.post("/me/room-requests", {"academic_year": YEAR}, me).json()
    assert c.post(f"/allocations/{req['id']}/cancel", {"reason": "no"}, me).status_code == 422  # min 3 chars
    _, stranger = c.org.user("hostel-resident")
    assert c.post(f"/allocations/{req['id']}/cancel", {"reason": "not mine"}, stranger).status_code == 404
    r = c.post(f"/allocations/{req['id']}/cancel", {"reason": "Staying at home"}, me)
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["cancel_reason"] == "Staying at home"
    assert events("hostel.allocation.cancelled", c.org.id)[-1]["was_confirmed"] is False

    req = c.post("/me/room-requests", {"academic_year": YEAR}, me).json()  # a new request is allowed now
    c.post(f"/allocations/{req['id']}/confirm", {"room_id": c.room["id"], "bed": "1"}, c.warden)
    assert c.post(f"/allocations/{req['id']}/cancel", {"reason": "Changed mind"}, me).status_code == 403
    r = c.post(f"/allocations/{req['id']}/cancel", {"reason": "Fees not paid"}, c.warden)
    assert r.status_code == 200 and events("hostel.allocation.cancelled", c.org.id)[-1]["was_confirmed"] is True

    _, _, occupied = c.resident("2")
    r = c.post(f"/allocations/{occupied['id']}/cancel", {"reason": "Too late"}, c.warden)
    assert r.status_code == 409


def test_room_change_is_check_out_then_new_allocation(campus):
    c = campus
    person_id, _, first = c.resident("1")
    c.post(f"/allocations/{first['id']}/check-out", None, c.warden)
    other = c.post(f"/hostels/{c.hostel['id']}/rooms", {"number": "104", "room_type": "single", "capacity": 1}, c.admin)
    body = {"person_id": person_id, "room_id": other.json()["id"], "bed": "1", "academic_year": YEAR}
    assert c.post("/allocations", {**body, "from": "2026-10-12", "to": "2027-05-31"}, c.warden).status_code == 201


def test_list_allocations_with_filters_and_pages(campus):
    c = campus
    for bed in ("1", "2"):
        c.resident(bed)
    page = c.get("/allocations?status=occupied&limit=1", c.viewer).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    rest = c.get(f"/allocations?status=occupied&limit=1&cursor={page['next_cursor']}", c.viewer).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert rest["items"][0]["id"] != page["items"][0]["id"]
    one = page["items"][0]
    assert c.get(f"/allocations/{one['id']}", c.viewer).json()["person_id"] == one["person_id"]
    assert c.get(f"/allocations?person_id={one['person_id']}", c.viewer).json()["items"][0]["id"] == one["id"]
    _, security = c.org.user("hostel-security")
    assert c.get("/allocations", security).status_code == 403


def test_my_allocation_is_empty_without_one(campus):
    _, me = campus.org.user("hostel-resident")
    assert campus.get("/me/allocation", me).json() == {"allocation": None, "hostel": None}


def test_an_occupied_bed_stays_held_after_its_planned_end_date(campus, monkeypatch):
    """A resident who has not checked out keeps the bed even when the allocation's to_date has passed."""
    c = campus
    _, me, alloc = c.resident("1")
    assert alloc["status"] == "occupied" and alloc["to"] is not None
    monkeypatch.setattr(service, "clock", lambda: datetime(2027, 6, 2, 8, 0, tzinfo=UTC))  # after `to`
    assert "1" not in c.get(f"/hostels/{c.hostel['id']}/rooms", c.warden).json()[0]["free_beds"]
    assert c.get(f"/hostels/{c.hostel['id']}", c.viewer).json()["beds_occupied"] == 1
    assert c.get("/me/allocation", me).json()["hostel"]["id"] == c.hostel["id"]
    other_id, _ = c.org.user("hostel-resident")
    body = {
        "person_id": other_id,
        "room_id": c.room["id"],
        "bed": "1",
        "academic_year": "2027-28",
        "from": "2027-06-02",
        "to": "2028-05-31",
    }
    r = c.post("/allocations", body, c.warden)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "bed_taken"
    r = c.client.patch(f"{BASE}/rooms/{c.room['id']}", json={"capacity": 1}, headers=c.admin)
    assert r.status_code in (409, 422)


def test_direct_allocation_refuses_a_person_with_an_open_request(campus):
    """One open request or allocation per person and year: staff confirm the request instead of adding a second row."""
    c = campus
    person_id, me = c.org.user("hostel-resident")
    req = c.post("/me/room-requests", {"academic_year": YEAR}, me).json()
    body = {
        "person_id": person_id,
        "room_id": c.room["id"],
        "bed": "2",
        "academic_year": YEAR,
        "from": "2026-10-12",
        "to": "2027-05-31",
    }
    r = c.post("/allocations", body, c.warden)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_requested"
    assert (
        c.post(f"/allocations/{req['id']}/confirm", {"room_id": c.room["id"], "bed": "2"}, c.warden).status_code == 200
    )
    assert [a["status"] for a in c.get(f"/allocations?person_id={person_id}", c.warden).json()["items"]] == [
        "confirmed"
    ]
