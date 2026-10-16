"""Mess menu, visitors and discipline incidents (docs/user-stories.md ME-1, ME-2, VI-1..VI-4, IN-1..IN-3)."""

from conftest import BASE, at
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from sqlalchemy import select


def test_set_and_read_the_mess_menu(campus, client):
    c = campus
    h = c.hostel["id"]
    day = [
        {"hostel_id": h, "date": "2026-10-12", "meal": "breakfast", "items": ["Idli", "Sambar"]},
        {"hostel_id": h, "date": "2026-10-12", "meal": "dinner", "items": ["Rice", "Dal"]},
    ]
    r = client.put(f"{BASE}/mess-menus", json=day, headers=c.admin)
    assert r.status_code == 200 and len(r.json()) == 2
    replace = [{"hostel_id": h, "date": "2026-10-12", "meal": "dinner", "items": ["Chapati"]}]
    client.put(f"{BASE}/mess-menus", json=replace, headers=c.admin)
    _, me, _ = c.resident()
    menu = c.get(f"/mess-menus?hostel_id={h}&from=2026-10-12&to=2026-10-12", me).json()
    assert {m["meal"]: m["items"] for m in menu} == {"breakfast": ["Idli", "Sambar"], "dinner": ["Chapati"]}
    assert c.get(f"/mess-menus?hostel_id={h}&from=2026-10-13&to=2026-10-12", me).status_code == 422
    assert c.get(f"/mess-menus?hostel_id={h}&from=2026-10-12", me).status_code == 422  # all three required
    assert client.put(f"{BASE}/mess-menus", json=replace, headers=c.warden).status_code == 403


def test_visitor_in_and_out(campus):
    c = campus
    person_id, me, _ = c.resident()
    body = {"person_id": person_id, "visitor_name": "A. Parent", "relation": "Mother", "id_document_note": "DL 4321"}
    r = c.post("/visits", body, c.security)
    assert r.status_code == 201 and r.json()["hostel_id"] == c.hostel["id"] and r.json()["out_at"] is None
    visit = r.json()
    r = c.post(f"/visits/{visit['id']}/out", None, c.security)
    assert r.status_code == 200 and r.json()["out_at"]
    assert c.post(f"/visits/{visit['id']}/out", None, c.security).status_code == 409
    log = c.get(f"/visits?person_id={person_id}&date=2026-10-12", c.warden).json()["items"]
    assert [v["id"] for v in log] == [visit["id"]]
    assert [v["id"] for v in c.get("/me/visits", me).json()] == [visit["id"]]
    _, other, _ = c.resident("2")
    assert c.get("/me/visits", other).json() == []


def test_visitor_rules(campus):
    c = campus
    person_id, _, _ = c.resident()
    full_number = {"person_id": person_id, "visitor_name": "X", "id_document_note": "Aadhaar 1234 5678 9012"}
    r = c.post("/visits", full_number, c.security)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "id_number_too_long"
    outsider, _ = c.org.user("hostel-resident")
    r = c.post("/visits", {"person_id": outsider, "visitor_name": "X"}, c.security)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_resident"
    assert c.post("/visits", {"person_id": person_id, "visitor_name": "X"}, c.viewer).status_code == 403
    assert c.post("/visits", {"person_id": person_id, "visitor_name": "X"}, c.admin).status_code == 403
    assert c.get("/visits", c.viewer).status_code == 403


def test_incidents_are_restricted_and_never_published(campus, client):
    c = campus
    person_id, me, _ = c.resident()
    body = {"person_id": person_id, "occurred_at": at(7), "category": "Curfew", "description": "Late by 2 hours"}
    r = c.post("/incidents", body, c.warden)
    assert r.status_code == 201 and r.json()["status"] == "open" and r.json()["hostel_id"] == c.hostel["id"]
    incident = r.json()
    r = client.patch(
        f"{BASE}/incidents/{incident['id']}", json={"action_taken": "Warning", "status": "closed"}, headers=c.warden
    )
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["closed_at"]
    assert c.get("/incidents?status=closed", c.admin).json()["items"][0]["action_taken"] == "Warning"
    for headers in (c.security, c.viewer, me):
        assert c.get("/incidents", headers).status_code == 403
    assert c.post("/incidents", body, c.security).status_code == 403
    with SessionLocal() as db:
        names = set(db.scalars(select(OutboxEvent.name).where(OutboxEvent.organisation_id == c.org.id)))
    assert not [n for n in names if "incident" in n or "visit" in n]
