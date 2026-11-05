"""Edge inputs answer 422 or 409, never a 500; roles that extend `student` request passes as students."""

import base64

from conftest import TERM, at
from eos_transport.infrastructure import repository


def test_a_role_extending_student_requests_as_a_student(campus):
    c = campus
    _, _, issued = c.rider(role="medical-student")
    assert issued["rider_type"] == "student"
    _, _, staff = c.rider(role="transport-rider")
    assert staff["rider_type"] == "staff"


def test_numbers_past_the_columns_are_refused(campus):
    c = campus
    huge = 2**63
    vehicle = {"registration_no": "KA09ZZ0001", "capacity": huge}
    assert c.post("/vehicles", vehicle, c.admin).status_code == 422
    assert c.post("/vehicles", {**vehicle, "capacity": 1001}, c.admin).status_code == 422
    v = c.vehicle
    body = {"registration_no": v["registration_no"], "capacity": huge}
    assert c.patch(f"/vehicles/{v['id']}", body, c.admin).status_code == 422
    stops = [{"stop_id": s["id"], "sequence": huge if i == 0 else i + 1} for i, s in enumerate(c.stops)]
    assert c.post("/routes", {"code": "BIG", "name": "Big", "stops": stops}, c.admin).status_code == 422
    for path in ("/vehicles", "/drivers"):
        assert c.get(f"{path}?expiring_within_days=1000000000", c.viewer).status_code == 422
        assert c.get(f"{path}?expiring_within_days=3650", c.viewer).status_code == 200
    trip = c.post("/trips", {"route_id": c.route["id"]}, c.driver).json()
    assert c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": huge}, c.driver).status_code == 422
    assert c.put(f"/trips/{trip['id']}/delay", {"delay_minutes": 1441}, c.driver).status_code == 422


def test_instants_at_the_ends_of_the_calendar_are_refused(campus):
    c = campus
    notice = {"kind": "general", "title": "Far", "body": "x", "expires_at": "9999-12-31T23:59:59-05:00"}
    assert c.post("/notices", notice, c.admin).status_code == 422
    trip = c.post("/trips", {"route_id": c.route["id"]}, c.driver).json()
    early = [{"recorded_at": "0001-01-01T00:30:00+01:00", "latitude": 12.9, "longitude": 77.6}]
    assert c.post(f"/trips/{trip['id']}/positions", early, c.driver).status_code == 422
    fine = [{"recorded_at": at(7, 5), "latitude": 12.9, "longitude": 77.6}]
    assert c.post(f"/trips/{trip['id']}/positions", fine, c.driver).status_code == 204


def test_a_cursor_we_never_handed_out_starts_from_the_top(campus):
    c = campus
    c.rider()
    first = c.get("/passes?limit=1", c.admin).json()
    for raw in (b"9223372036854775808", b"99999999999999999999", b"-5"):
        cursor = base64.urlsafe_b64encode(raw).decode()
        r = c.get(f"/passes?limit=1&cursor={cursor}", c.admin)
        assert r.status_code == 200, r.text
        assert r.json() == first


def test_a_duplicate_that_slips_past_the_check_is_a_conflict(campus, monkeypatch):
    """Two requests at once both pass the lookup; the unique constraint catches the second one."""
    c = campus
    monkeypatch.setattr(repository, "route_by_code", lambda db, code: None)
    monkeypatch.setattr(repository, "vehicle_by_registration", lambda db, reg: None)
    stops = [{"stop_id": s["id"], "sequence": i + 1} for i, s in enumerate(c.stops)]
    r = c.post("/routes", {"code": "R1", "name": "Again", "stops": stops}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_exists"
    r2 = c.new_route("R2")
    r = c.patch(f"/routes/{r2['id']}", {"code": "R1", "name": "Clash", "stops": stops}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_exists"
    r = c.post("/vehicles", {"registration_no": "KA01AB1234", "capacity": 4}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "vehicle_exists"
    # The organisation is still usable after the refused writes.
    assert c.post("/vehicles", {"registration_no": "KA01AB9999", "capacity": 4}, c.admin).status_code == 201


def test_stop_search_takes_wildcards_literally(campus):
    c = campus
    assert c.get("/stops?q=%25", c.viewer).json() == []
    assert c.get("/stops?q=_", c.viewer).json() == []
    c.post("/stops", {"name": "Gate 5_A"}, c.admin)
    assert [s["name"] for s in c.get("/stops?q=5_", c.viewer).json()] == ["Gate 5_A"]


def test_pass_request_after_a_refused_one_still_works(campus):
    c = campus
    person, headers = c.org.user("transport-rider")
    body = {"route_id": c.route["id"], "stop_id": c.stops[0]["id"], **TERM}
    assert c.post("/me/passes", body, headers).status_code == 201
    assert c.post("/me/passes", body, headers).status_code == 409
