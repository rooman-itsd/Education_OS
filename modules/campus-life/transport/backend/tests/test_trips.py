"""Trips, positions, delays and the live view (docs/user-stories.md TR, LV)."""

from conftest import at, events
from eos_transport.infrastructure.models import new_id


def start(c):
    r = c.post("/trips", {"route_id": c.route["id"]}, c.driver)
    assert r.status_code == 201, r.text
    return r.json()


def test_driver_runs_a_trip(campus):
    c = campus
    trip = start(c)
    assert trip["status"] == "running" and trip["vehicle_id"] == c.vehicle["id"] and trip["delay_minutes"] == 0
    assert events("transport.trip.started", c.org.id)[-1]["trip_id"] == trip["id"]
    r = c.post("/trips", {"route_id": c.route["id"]}, c.driver)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "trip_running"

    positions = [{"recorded_at": at(7, m), "latitude": 12.9 + m / 1000, "longitude": 77.6} for m in (1, 2)]
    assert c.post(f"/trips/{trip['id']}/positions", positions, c.driver).status_code == 204
    assert c.post(f"/trips/{trip['id']}/positions", [], c.driver).status_code == 422
    too_many = [positions[0]] * 101
    assert c.post(f"/trips/{trip['id']}/positions", too_many, c.driver).status_code == 422
    bad = [{"recorded_at": at(7), "latitude": 200, "longitude": 77.6}]
    assert c.post(f"/trips/{trip['id']}/positions", bad, c.driver).status_code == 422

    r = c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": 10, "note": "Traffic"}, c.driver)
    assert r.status_code == 200 and r.json()["delay_minutes"] == 10
    c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": 5}, c.driver)  # shorter: no new event
    c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": 15}, c.driver)
    delays = [e["delay_minutes"] for e in events("transport.trip.delayed", c.org.id)]
    assert delays == [10, 15]
    assert c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": -1}, c.driver).status_code == 422

    r = c.post(f"/trips/{trip['id']}/end", None, c.driver)
    assert r.status_code == 200 and r.json()["status"] == "completed" and r.json()["ended_at"]
    assert events("transport.trip.completed", c.org.id)[-1]["trip_id"] == trip["id"]
    assert c.post(f"/trips/{trip['id']}/end", None, c.driver).status_code == 409
    assert c.post(f"/trips/{trip['id']}/positions", positions, c.driver).status_code == 409
    assert start(c)["id"] != trip["id"]  # a new trip after the last one ended


def test_only_the_routes_driver_records(campus):
    c = campus
    other_person, other_driver = c.org.user("transport-driver")
    c.post(
        "/drivers",
        {"person_id": other_person, "name": "Other", "licence_no": "DL-3", "licence_expires_on": "2030-01-01"},
        c.admin,
    )
    r = c.post("/trips", {"route_id": c.route["id"]}, other_driver)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_route_driver"
    trip = start(c)
    pos = [{"recorded_at": at(7), "latitude": 12.9, "longitude": 77.6}]
    assert c.post(f"/trips/{trip['id']}/positions", pos, other_driver).status_code == 409
    assert c.post(f"/trips/{trip['id']}/end", None, other_driver).status_code == 409
    assert c.post("/trips", {"route_id": c.route["id"]}, c.admin).status_code == 403  # no tracking:record
    assert c.post("/trips", {"route_id": new_id()}, c.driver).status_code == 404


def test_trip_refused_when_documents_lapsed_after_assignment(campus):
    c = campus
    c.patch(
        f"/vehicles/{c.vehicle['id']}",
        {"registration_no": "KA01AB1234", "capacity": 2, "insurance_expires_on": "2026-10-01"},
        c.admin,
    )
    r = c.post("/trips", {"route_id": c.route["id"]}, c.driver)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "document_expired"


def test_live_view_for_staff_and_pass_holders(campus):
    c = campus
    _, holder, _ = c.rider()
    _, stranger = c.org.user("transport-rider")
    path = f"/routes/{c.route['id']}/live"
    assert c.get(path, c.viewer).json() is None  # no trip running
    trip = start(c)
    live = c.get(path, holder).json()
    assert live["id"] == trip["id"] and live["last_position"] is None and live["next_stop_id"] is None
    c.post(
        f"/trips/{trip['id']}/positions",
        [{"recorded_at": at(7, 5), "latitude": 12.94, "longitude": 77.6, "speed_kmh": 30}],
        c.driver,
    )
    c.post(
        f"/trips/{trip['id']}/positions", [{"recorded_at": at(7, 1), "latitude": 12.90, "longitude": 77.6}], c.driver
    )
    live = c.get(path, c.viewer).json()
    assert live["last_position"]["latitude"] == 12.94  # latest by recorded_at, not by arrival
    assert live["next_stop_id"] == c.stops[1]["id"]
    r = c.get(path, stranger)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "no_pass"
    assert c.get(path, c.driver).status_code == 403  # drivers record; they do not hold tracking:read
    c.post(f"/trips/{trip['id']}/end", None, c.driver)
    assert c.get(path, holder).json() is None
