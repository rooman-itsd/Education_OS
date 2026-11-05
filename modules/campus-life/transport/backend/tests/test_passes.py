"""Pass requests, issue, reject, cancel and capacity (docs/user-stories.md PA)."""

from conftest import TERM, events
from eos_transport.infrastructure.models import new_id


def request(c, headers, stop: int = 0, **over):
    return c.post("/me/passes", {"route_id": c.route["id"], "stop_id": c.stops[stop]["id"], **TERM, **over}, headers)


def test_request_and_issue_publish_events(campus):
    c = campus
    person_id, me = c.org.user("transport-rider")
    r = request(c, me, stop=1)
    assert r.status_code == 201
    p = r.json()
    assert p["status"] == "requested" and p["person_id"] == person_id and p["rider_type"] == "staff"
    assert p["route_code"] == "R1" and p["stop_name"] == "Market"
    assert events("transport.pass.requested", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "pass_id": p["id"],
        "person_id": person_id,
        "route_id": c.route["id"],
        "stop_id": c.stops[1]["id"],
        "valid_from": "2026-10-27",
        "valid_to": "2027-03-31",
    }
    r = c.post(f"/passes/{p['id']}/decision", {"decision": "issued"}, c.admin)
    assert r.status_code == 200 and r.json()["status"] == "issued" and r.json()["decided_by"] is not None
    issued = events("transport.pass.issued", c.org.id)[-1]
    assert issued["pass_id"] == p["id"] and issued["rider_type"] == "staff" and issued["stop_id"] == c.stops[1]["id"]
    assert c.post(f"/passes/{p['id']}/decision", {"decision": "issued"}, c.admin).status_code == 409
    assert c.get("/passes?status=issued", c.viewer).json()["items"][0]["id"] == p["id"]


def test_request_validation(campus):
    c = campus
    _, me = c.org.user("transport-rider")
    elsewhere = c.post("/stops", {"name": "Elsewhere"}, c.admin).json()
    r = c.post("/me/passes", {"route_id": c.route["id"], "stop_id": elsewhere["id"], **TERM}, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "stop_not_on_route"
    assert request(c, me, valid_to="2026-10-01").status_code == 422
    assert request(c, me, valid_from="2026-01-01", valid_to="2026-02-01").status_code == 422  # in the past
    assert request(c, me, route_id=new_id()).status_code == 404
    assert request(c, me, route_id="R1").status_code == 422
    assert request(c, me).status_code == 201
    r = request(c, me, valid_from="2027-01-01", valid_to="2027-06-30")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "overlapping_pass"
    assert request(c, me, valid_from="2027-04-01", valid_to="2027-06-30").status_code == 201  # the next term


def test_inactive_route_takes_no_passes(campus):
    c = campus
    c.patch(
        f"/routes/{c.route['id']}", {"code": "R1", "name": "R1", "stops": c.route["stops"], "active": False}, c.admin
    )
    _, me = c.org.user("transport-rider")
    r = request(c, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_inactive"


def test_capacity_needs_override_with_reason(campus):
    c = campus
    c.rider()
    c.rider()  # the van's two seats
    _, me = c.org.user("transport-rider")
    third = request(c, me).json()
    path = f"/passes/{third['id']}/decision"
    r = c.post(path, {"decision": "issued"}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_full"
    assert c.post(path, {"decision": "issued", "override_capacity": True}, c.admin).status_code == 422
    r = c.post(path, {"decision": "issued", "override_capacity": True, "reason": "Exam week"}, c.admin)
    assert r.status_code == 200 and r.json()["status"] == "issued"
    assert c.get(f"/routes/{c.route['id']}", c.admin).json()["passes_issued"] == 3


def test_passes_that_do_not_overlap_in_time_share_a_seat(campus):
    c = campus
    c.rider()
    c.rider()
    _, me = c.org.user("transport-rider")
    later = request(c, me, valid_from="2027-04-01", valid_to="2027-06-30").json()
    assert c.post(f"/passes/{later['id']}/decision", {"decision": "issued"}, c.admin).status_code == 200


def test_issue_direct(campus):
    c = campus
    person = new_id()
    body = {"person_id": person, "route_id": c.route["id"], "stop_id": c.stops[0]["id"], **TERM}
    r = c.post("/passes", body, c.admin)
    assert r.status_code == 201 and r.json()["rider_type"] == "student" and r.json()["status"] == "issued"
    assert c.post("/passes", body, c.admin).status_code == 409  # overlapping
    staff = c.post("/passes", {**body, "person_id": new_id(), "rider_type": "staff"}, c.admin)
    assert staff.status_code == 201 and events("transport.pass.issued", c.org.id)[-1]["rider_type"] == "staff"
    r = c.post("/passes", {**body, "person_id": new_id()}, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_full"
    assert c.post("/passes", {**body, "person_id": new_id(), "rider_type": "guest"}, c.admin).status_code == 422
    assert c.post("/passes", {**body, "person_id": new_id()}, c.viewer).status_code == 403


def test_route_without_vehicle_needs_override(campus):
    c = campus
    bare = c.new_route("R9")
    body = {"person_id": new_id(), "route_id": bare["id"], "stop_id": c.stops[0]["id"], **TERM}
    r = c.post("/passes", body, c.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "route_full"
    assert (
        c.post("/passes", {**body, "override_capacity": True, "reason": "Van from Monday"}, c.admin).status_code == 201
    )


def test_reject_needs_reason(campus):
    c = campus
    person_id, me = c.org.user("transport-rider")
    p = request(c, me).json()
    path = f"/passes/{p['id']}/decision"
    assert c.post(path, {"decision": "rejected"}, c.admin).status_code == 422
    r = c.post(path, {"decision": "rejected", "reason": "Outside the service area"}, c.admin)
    assert (
        r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reason"] == "Outside the service area"
    )
    assert events("transport.pass.rejected", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "pass_id": p["id"],
        "person_id": person_id,
        "reason": "Outside the service area",
    }
    assert c.post(path, {"decision": "maybe"}, c.admin).status_code == 422


def test_cancel_own_or_by_office(campus):
    c = campus
    person_id, me, issued = c.rider()
    _, someone = c.org.user("transport-rider")
    assert c.post(f"/passes/{issued['id']}/cancel", {"reason": "Not mine"}, someone).status_code == 404
    assert c.post(f"/passes/{issued['id']}/cancel", {"reason": "x"}, me).status_code == 422  # reason too short
    r = c.post(f"/passes/{issued['id']}/cancel", {"reason": "Moved closer"}, me)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert events("transport.pass.cancelled", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "pass_id": issued["id"],
        "person_id": person_id,
        "route_id": c.route["id"],
        "cancelled_on": "2026-10-27",
        "reason": "Moved closer",
    }
    assert c.post(f"/passes/{issued['id']}/cancel", {"reason": "Again"}, c.admin).status_code == 409

    _, other = c.org.user("transport-rider")
    req = request(c, other).json()
    before = len(events("transport.pass.cancelled", c.org.id))
    assert c.post(f"/passes/{req['id']}/cancel", {"reason": "Not needed"}, c.admin).json()["status"] == "cancelled"
    assert len(events("transport.pass.cancelled", c.org.id)) == before  # a withdrawn request was never issued


def test_my_passes_current_first_and_list_paging(campus):
    c = campus
    _, me, current = c.rider()
    nxt = request(c, me, valid_from="2027-04-01", valid_to="2027-06-30").json()
    old = request(c, me, valid_from="2027-07-01", valid_to="2027-08-30").json()
    c.post(f"/passes/{old['id']}/cancel", {"reason": "Changed plans"}, me)
    assert [p["id"] for p in c.get("/me/passes", me).json()] == [current["id"], nxt["id"], old["id"]]
    first = c.get("/passes?limit=2", c.admin).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = c.get(f"/passes?limit=2&cursor={first['next_cursor']}", c.admin).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert c.get(f"/passes?route_id={c.route['id']}&status=requested", c.viewer).json()["items"][0]["id"] == nxt["id"]
    assert c.get("/passes", me).status_code == 403
