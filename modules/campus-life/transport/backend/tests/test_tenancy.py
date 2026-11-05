"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, TERM, Campus, at
from eos_testing import assert_no_cross_tenant_leak
from eos_transport.infrastructure.models import new_id


def seed(client, org) -> tuple[Campus, dict]:
    c = Campus(client, org)
    _, me, issued = c.rider()
    trip = c.post("/trips", {"route_id": c.route["id"]}, c.driver).json()
    c.post(f"/trips/{trip['id']}/positions", [{"recorded_at": at(7), "latitude": 12.9, "longitude": 77.6}], c.driver)
    notice = c.post("/notices", {"kind": "general", "title": "Hello", "body": "x", "route_id": c.route["id"]}, c.admin)
    return c, {"me": me, "pass": issued["id"], "trip": trip["id"], "notice": notice.json()["id"]}


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def test_no_cross_tenant_leak(client, org, other_org):
    a, a_ids = seed(client, org)
    b, b_ids = seed(client, other_org)
    lists = [
        ("/stops", a.admin, b.admin),
        ("/routes", a.admin, b.admin),
        ("/vehicles", a.admin, b.admin),
        ("/drivers", a.admin, b.admin),
        ("/passes", a.admin, b.admin),
        ("/notices", a.admin, b.admin),
        ("/me/passes", a_ids["me"], b_ids["me"]),
        ("/me/notices", a_ids["me"], b_ids["me"]),
    ]
    for path, ha, hb in lists:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))


def test_another_organisations_records_are_not_found(client, org, other_org):
    a, ids = seed(client, org)
    b = Campus(client, other_org)
    route, stop, vehicle, driver = a.route["id"], a.stops[0]["id"], a.vehicle["id"], a.driver_row["id"]
    for path in (f"/routes/{route}", f"/routes/{route}/live"):
        assert client.get(f"{BASE}{path}", headers=b.admin).status_code == 404, path
    posts = [
        (f"/passes/{ids['pass']}/cancel", {"reason": "steal"}, b.admin),
        (f"/notices/{ids['notice']}/withdraw", None, b.admin),
        ("/passes", {"person_id": new_id(), "route_id": route, "stop_id": stop, **TERM}, b.admin),
        ("/notices", {"kind": "general", "title": "x", "body": "x", "route_id": route}, b.admin),
        ("/trips", {"route_id": route}, b.driver),
        (f"/trips/{ids['trip']}/end", None, b.driver),
        (f"/trips/{ids['trip']}/positions", [{"recorded_at": at(7), "latitude": 1, "longitude": 1}], b.driver),
    ]
    for path, body, headers in posts:
        assert client.post(f"{BASE}{path}", json=body, headers=headers).status_code == 404, path
    _, rider_b = other_org.user("transport-rider")
    body = {"route_id": route, "stop_id": stop, **TERM}
    assert client.post(f"{BASE}/me/passes", json=body, headers=rider_b).status_code == 404
    patches = [
        (f"/stops/{stop}", {"name": "x"}),
        (f"/routes/{route}", {"code": "X", "name": "X", "stops": a.route["stops"]}),
        (f"/vehicles/{vehicle}", {"registration_no": "X", "capacity": 4}),
        (f"/drivers/{driver}", {"name": "x", "licence_no": "x", "licence_expires_on": "2030-01-01"}),
    ]
    for path, body in patches:
        assert client.patch(f"{BASE}{path}", json=body, headers=b.admin).status_code == 404, path
    # B cannot assign A's vehicle and driver to B's own route either.
    assignment = {"vehicle_id": vehicle, "driver_id": driver}
    assert client.put(f"{BASE}/routes/{b.route['id']}/assignment", json=assignment, headers=b.admin).status_code == 404
    # A's route still has A's assignment.
    assert client.get(f"{BASE}/routes/{route}", headers=a.admin).json()["vehicle_id"] == vehicle
