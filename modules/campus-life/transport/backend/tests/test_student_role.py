"""A normal student holds only the profile role `student` (identity's default). The student layout lists
`transport-rider` in `module_roles`, so that role alone carries the transport self-service keys. These tests use real
`student` tokens; the rest of the suite mints `transport-rider`, which must keep working."""

from conftest import BASE, TERM, Campus
from eos_core.config import permissions_for
from eos_testing import assert_no_cross_tenant_leak
from eos_transport.infrastructure.models import new_id

SELF = {"transport:self:read", "transport:self:request"}


def transport_keys(roles: list[str]) -> set[str]:
    return {p for p in permissions_for(roles) if p.startswith("transport:")}


def test_student_gets_exactly_the_self_service_keys():
    assert transport_keys(["student"]) == SELF
    assert transport_keys(["transport-rider"]) == SELF
    assert transport_keys(["student", "transport-rider"]) == SELF
    assert transport_keys(["org-admin"]) == set()
    assert transport_keys(["applicant"]) == set()


def test_student_uses_self_service(campus):
    c = campus
    person_id, me, issued = c.rider(role="student")
    assert issued["person_id"] == person_id and issued["rider_type"] == "student"
    assert [p["id"] for p in c.get("/me/passes", me).json()] == [issued["id"]]
    assert c.get("/me/notices", me).status_code == 200
    assert c.get("/stops", me).status_code == 200 and c.get("/routes", me).status_code == 200
    assert c.get(f"/routes/{c.route['id']}/live", me).status_code == 200
    assert c.post(f"/passes/{issued['id']}/cancel", {"reason": "Moving"}, me).json()["status"] == "cancelled"


def test_student_cannot_touch_another_students_pass(campus):
    c = campus
    _, a, _ = c.rider(role="student")
    _, _, b_pass = c.rider(role="student")
    assert c.post(f"/passes/{b_pass['id']}/cancel", {"reason": "not mine"}, a).status_code == 404
    assert all(p["id"] != b_pass["id"] for p in c.get("/me/passes", a).json())


def test_student_cannot_use_staff_operations(campus, client):
    c = campus
    _, me, p = c.rider(role="student")
    for path in ("/vehicles", "/drivers", "/passes", "/notices", f"/routes/{c.route['id']}"):
        assert c.get(path, me).status_code == 403, path
    posts = [
        ("/stops", {"name": "x"}),
        ("/routes", {"code": "X", "name": "X", "stops": c.route["stops"]}),
        ("/vehicles", {"registration_no": "X", "capacity": 4}),
        ("/drivers", {"name": "x", "licence_no": "x", "licence_expires_on": "2030-01-01"}),
        ("/passes", {"person_id": new_id(), "route_id": c.route["id"], "stop_id": c.stops[0]["id"], **TERM}),
        (f"/passes/{p['id']}/decision", {"decision": "issued"}),
        ("/trips", {"route_id": c.route["id"]}),
        ("/notices", {"kind": "general", "title": "x", "body": "x"}),
    ]
    for path, body in posts:
        assert c.post(path, body, me).status_code == 403, path
    assignment = {"vehicle_id": c.vehicle["id"], "driver_id": c.driver_row["id"]}
    assert client.put(f"{BASE}/routes/{c.route['id']}/assignment", json=assignment, headers=me).status_code == 403


def test_students_of_two_organisations_never_see_each_other(client, org, other_org):
    a, b = Campus(client, org), Campus(client, other_org)
    _, me_a, pass_a = a.rider(role="student")
    _, me_b, _ = b.rider(role="student")
    for c in (a, b):
        c.post("/notices", {"kind": "general", "title": "Hello", "body": "x", "route_id": c.route["id"]}, c.admin)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/me/notices", "/me/passes", "/stops", "/routes"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(me_a), token(me_b))
    assert (
        client.post(f"{BASE}/passes/{pass_a['id']}/cancel", json={"reason": "steal"}, headers=me_b).status_code == 404
    )
    assert client.get(f"{BASE}/routes/{a.route['id']}/live", headers=me_b).status_code == 404
