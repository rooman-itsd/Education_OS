"""Stops, routes, vehicles, drivers and route assignment (docs/user-stories.md ST, RO, FL, AS)."""

from conftest import BASE, events
from eos_transport.infrastructure.models import new_id


def test_stops_create_search_and_move(campus):
    c = campus
    assert c.post("/stops", {"name": "Bad", "latitude": 91}, c.admin).status_code == 422
    names = [s["name"] for s in c.get("/stops?q=mar", c.viewer).json()]
    assert names == ["Market"]
    stop = c.stops[0]
    r = c.patch(f"/stops/{stop['id']}", {"name": "North Gate", "latitude": 12.91}, c.admin)
    assert r.status_code == 200 and r.json()["name"] == "North Gate" and r.json()["longitude"] == 77.6
    assert c.patch(f"/stops/{new_id()}", {"name": "x"}, c.admin).status_code == 404
    assert c.post("/stops", {"name": "x"}, c.viewer).status_code == 403
    assert c.patch(f"/stops/{stop['id']}", {"name": "x"}, c.driver).status_code == 403


def test_route_stops_in_order_with_names(campus):
    c = campus
    route = c.get(f"/routes/{c.route['id']}", c.viewer).json()
    assert [s["stop_name"] for s in route["stops"]] == ["Main Gate", "Market", "Station"]
    assert [s["scheduled_time"] for s in route["stops"]] == ["07:00", "07:10", "07:20"]
    assert route["vehicle_registration_no"] == "KA01AB1234" and route["driver_name"] == "Test Driver"
    assert route["capacity"] == 2 and route["passes_issued"] == 0


def test_route_validation(campus):
    c = campus
    one_stop = {"code": "X", "name": "X", "stops": [{"stop_id": c.stops[0]["id"], "sequence": 1}]}
    assert c.post("/routes", one_stop, c.admin).status_code == 422
    dup = [{"stop_id": c.stops[0]["id"], "sequence": 1}, {"stop_id": c.stops[0]["id"], "sequence": 2}]
    assert c.post("/routes", {**one_stop, "stops": dup}, c.admin).status_code == 422
    unknown = [{"stop_id": c.stops[0]["id"], "sequence": 1}, {"stop_id": new_id(), "sequence": 2}]
    assert c.post("/routes", {**one_stop, "stops": unknown}, c.admin).status_code == 404
    bad_time = [{"stop_id": c.stops[0]["id"], "sequence": 1, "scheduled_time": "25:00"}, dup[1]]
    assert c.post("/routes", {**one_stop, "stops": bad_time}, c.admin).status_code == 422
    two = [{"stop_id": c.stops[0]["id"], "sequence": 1}, {"stop_id": c.stops[1]["id"], "sequence": 2}]
    assert c.post("/routes", {"code": "R1", "name": "Again", "stops": two}, c.admin).status_code == 409


def test_list_routes_filters(campus):
    c = campus
    other = c.new_route("R2", c.stops[1:])
    c.patch(
        f"/routes/{other['id']}", {"code": "R2", "name": "Route R2", "stops": other["stops"], "active": False}, c.admin
    )
    assert [r["code"] for r in c.get("/routes", c.viewer).json()] == ["R1", "R2"]
    assert [r["code"] for r in c.get("/routes?active=true", c.viewer).json()] == ["R1"]
    assert [r["code"] for r in c.get(f"/routes?stop_id={c.stops[0]['id']}", c.viewer).json()] == ["R1"]
    _, rider = c.org.user("transport-rider")
    assert c.get("/routes", rider).status_code == 200
    assert c.get(f"/routes/{c.route['id']}", rider).status_code == 403  # detail is for staff


def test_update_route_cannot_drop_a_boarding_stop(campus):
    c = campus
    c.rider(stop=2)
    keep_two = [{"stop_id": c.stops[0]["id"], "sequence": 1}, {"stop_id": c.stops[1]["id"], "sequence": 2}]
    body = {"code": "R1", "name": "Route R1", "stops": keep_two}
    r = c.patch(f"/routes/{c.route['id']}", body, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "stop_in_use"
    reordered = [
        {"stop_id": c.stops[2]["id"], "sequence": 1},
        {"stop_id": c.stops[0]["id"], "sequence": 2},
        {"stop_id": c.stops[1]["id"], "sequence": 3},
    ]
    r = c.patch(f"/routes/{c.route['id']}", {**body, "name": "Renamed", "stops": reordered}, c.admin)
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed" and [s["stop_name"] for s in r.json()["stops"]] == [
        "Station",
        "Main Gate",
        "Market",
    ]
    assert r.json()["direction"] == "morning pick-up"  # not sent, so kept


def test_vehicles(campus):
    c = campus
    body = {"registration_no": "KA01AB1234", "capacity": 40}
    assert c.post("/vehicles", body, c.admin).status_code == 409
    bus = c.post(
        "/vehicles", {"registration_no": "KA02CD5678", "capacity": 40, "insurance_expires_on": "2026-11-10"}, c.admin
    ).json()
    assert bus["active"] is True and bus["type"] is None
    assert [v["id"] for v in c.get("/vehicles?expiring_within_days=30", c.viewer).json()] == [bus["id"]]
    assert c.get("/vehicles?expiring_within_days=-1", c.viewer).status_code == 422
    r = c.patch(f"/vehicles/{bus['id']}", {"registration_no": "KA02CD5678", "capacity": 40, "active": False}, c.admin)
    assert r.json()["active"] is False and r.json()["insurance_expires_on"] == "2026-11-10"
    assert [v["id"] for v in c.get("/vehicles?active=false", c.viewer).json()] == [bus["id"]]
    clash = {"registration_no": "KA01AB1234", "capacity": 40}
    assert c.patch(f"/vehicles/{bus['id']}", clash, c.admin).status_code == 409
    assert c.post("/vehicles", {"registration_no": "X", "capacity": 0}, c.admin).status_code == 422
    assert c.post("/vehicles", {"registration_no": "X", "capacity": 4}, c.viewer).status_code == 403
    _, rider = c.org.user("transport-rider")
    assert c.get("/vehicles", rider).status_code == 403


def test_vehicle_capacity_cannot_drop_below_issued_passes(campus):
    c = campus
    c.rider()
    c.rider()
    body = {"registration_no": "KA01AB1234", "capacity": 1}
    r = c.patch(f"/vehicles/{c.vehicle['id']}", body, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "capacity_below_passes"
    assert c.patch(f"/vehicles/{c.vehicle['id']}", {**body, "capacity": 30}, c.admin).status_code == 200


def test_drivers(campus):
    c = campus
    soon = c.post(
        "/drivers", {"name": "Second Driver", "licence_no": "DL-2", "licence_expires_on": "2026-11-01"}, c.admin
    ).json()
    assert soon["person_id"] is None
    assert [d["id"] for d in c.get("/drivers?expiring_within_days=10", c.viewer).json()] == [soon["id"]]
    r = c.patch(
        f"/drivers/{soon['id']}",
        {"name": "Second Driver", "licence_no": "DL-2", "licence_expires_on": "2031-01-01"},
        c.admin,
    )
    assert r.status_code == 200 and c.get("/drivers?expiring_within_days=10", c.viewer).json() == []
    assert c.post("/drivers", {"name": "x", "licence_no": "x"}, c.admin).status_code == 422
    assert (
        c.post(
            "/drivers", {"name": "x", "licence_no": "x", "licence_expires_on": "2030-01-01", "person_id": "me"}, c.admin
        ).status_code
        == 422
    )


def test_assignment_refuses_expired_documents_and_publishes_changes(campus):
    c = campus
    assert events("transport.route.reassigned", c.org.id) == [
        {
            "organisation_id": c.org.id,
            "route_id": c.route["id"],
            "vehicle_id": c.vehicle["id"],
            "driver_id": c.driver_row["id"],
        }
    ]
    old = c.post(
        "/vehicles", {"registration_no": "OLD1", "capacity": 10, "fitness_expires_on": "2026-10-26"}, c.admin
    ).json()
    expired_driver = c.post(
        "/drivers", {"name": "Lapsed", "licence_no": "DL-9", "licence_expires_on": "2026-10-01"}, c.admin
    ).json()
    path = f"/routes/{c.route['id']}/assignment"
    r = c.put(path, {"vehicle_id": old["id"], "driver_id": c.driver_row["id"]}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "document_expired"
    r = c.put(path, {"vehicle_id": c.vehicle["id"], "driver_id": expired_driver["id"]}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "document_expired"
    assert c.put(path, {"vehicle_id": new_id(), "driver_id": c.driver_row["id"]}, c.admin).status_code == 404
    # Same assignment again: nothing changed, no second event.
    assert c.put(path, {"vehicle_id": c.vehicle["id"], "driver_id": c.driver_row["id"]}, c.admin).status_code == 200
    assert len(events("transport.route.reassigned", c.org.id)) == 1
    assert c.put(path, {"vehicle_id": c.vehicle["id"], "driver_id": c.driver_row["id"]}, c.viewer).status_code == 403


def test_unauthenticated_is_refused(client):
    assert client.get(f"{BASE}/routes").status_code == 401
    assert client.get(f"{BASE}/routes", headers={"Authorization": "Bearer nope"}).status_code == 401
