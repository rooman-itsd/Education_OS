"""A normal student holds only the profile role `student` (identity's default). Contract 0.2.0 grants the hostel
self-service keys to that role directly, so no hostel-specific role is needed. These tests use real `student`
tokens; the rest of the suite mints `hostel-resident`, which must keep working."""

from conftest import BASE, YEAR, at
from eos_core.config import permissions_for
from eos_hostel.infrastructure.models import new_id
from eos_testing import assert_no_cross_tenant_leak

SELF = {"hostel:self:read", "hostel:self:request"}


def hostel_keys(roles: list[str]) -> set[str]:
    return {p for p in permissions_for(roles) if p.startswith("hostel:")}


def test_student_gets_exactly_the_self_service_keys():
    assert hostel_keys(["student"]) == SELF
    assert hostel_keys(["hostel-resident"]) == SELF
    assert hostel_keys(["student", "hostel-resident"]) == SELF
    assert hostel_keys(["org-admin"]) == set()
    assert hostel_keys(["applicant"]) == set()


def test_student_uses_self_service(campus):
    c = campus
    person_id, me = c.org.user("student")
    assert c.get("/me/allocation", me).json() == {"allocation": None, "hostel": None}
    assert c.get("/me/notices", me).status_code == 200
    assert c.get("/me/leave-requests", me).json() == []
    assert c.get("/me/visits", me).json() == []
    req = c.post("/me/room-requests", {"academic_year": YEAR}, me)
    assert req.status_code == 201 and req.json()["person_id"] == person_id
    assert c.post(f"/allocations/{req.json()['id']}/cancel", {"reason": "Staying home"}, me).status_code == 200

    _, me, _ = c.resident(role="student")
    lv = c.post("/me/leave-requests", {"from": at(14), "to": at(18), "destination": "Home", "reason": "Visit"}, me)
    assert lv.status_code == 201
    assert c.post(f"/me/leave-requests/{lv.json()['id']}/withdraw", None, me).json()["status"] == "withdrawn"
    menu = f"/mess-menus?hostel_id={c.hostel['id']}&from=2026-10-12&to=2026-10-12"
    assert c.get(menu, me).status_code == 200


def test_student_cannot_touch_another_students_records(campus):
    c = campus
    _, a, _ = c.resident("1", role="student")
    b_id, b, _ = c.resident("2", role="student")
    b_leave = c.post("/me/leave-requests", {"from": at(14), "to": at(18), "destination": "x", "reason": "x"}, b).json()
    b_request = c.post("/me/room-requests", {"academic_year": "2027-28"}, b).json()
    c.post("/visits", {"person_id": b_id, "visitor_name": "Guest"}, c.security)

    assert c.post(f"/me/leave-requests/{b_leave['id']}/withdraw", None, a).status_code == 404
    assert c.post(f"/allocations/{b_request['id']}/cancel", {"reason": "not mine"}, a).status_code == 404
    assert c.get("/me/leave-requests", a).json() == []
    assert c.get("/me/visits", a).json() == []
    assert c.get("/me/allocation", a).json()["allocation"]["person_id"] != b_id


def test_student_cannot_use_staff_operations(campus, client):
    c = campus
    _, me, alloc = c.resident(role="student")
    lv = c.post("/me/leave-requests", {"from": at(14), "to": at(18), "destination": "x", "reason": "x"}, me).json()
    gets = [
        "/hostels",
        f"/hostels/{c.hostel['id']}",
        "/allocations",
        "/leave-requests",
        "/visits",
        "/incidents",
        "/notices",
    ]
    for path in gets:
        assert c.get(path, me).status_code == 403, path
    posts = [
        ("/hostels", {"name": "X", "occupancy_type": "men"}),
        (
            "/allocations",
            {
                "person_id": new_id(),
                "room_id": c.room["id"],
                "bed": "2",
                "academic_year": YEAR,
                "from": "2026-10-12",
                "to": "2027-05-31",
            },
        ),
        (f"/allocations/{alloc['id']}/check-out", None),
        (f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}),
        (f"/leave-requests/{lv['id']}/return", None),
        (f"/leave-requests/{lv['id']}/gate-out", None),
        ("/visits", {"person_id": new_id(), "visitor_name": "x"}),
        ("/incidents", {"person_id": new_id(), "occurred_at": at(7), "category": "x", "description": "x"}),
        ("/notices", {"title": "x", "body": "x"}),
    ]
    for path, body in posts:
        assert c.post(path, body, me).status_code == 403, path
    assert client.patch(f"{BASE}/rooms/{c.room['id']}", json={"capacity": 5}, headers=me).status_code == 403
    assert client.put(f"{BASE}/mess-menus", json=[], headers=me).status_code == 403


def test_students_of_two_organisations_never_see_each_other(client, org, other_org):
    from conftest import Campus

    a, b = Campus(client, org), Campus(client, other_org)
    _, me_a, alloc_a = a.resident(role="student")
    _, me_b, _ = b.resident(role="student")
    for c, me in ((a, me_a), (b, me_b)):
        c.post("/notices", {"title": "Hello", "body": "x", "hostel_id": c.hostel["id"]}, c.warden)
        c.post("/me/leave-requests", {"from": at(14), "to": at(18), "destination": "x", "reason": "x"}, me)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/me/notices", "/me/leave-requests", "/me/visits"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(me_a), token(me_b))
    leave_a = client.get(f"{BASE}/me/leave-requests", headers=me_a).json()[0]
    assert client.post(f"{BASE}/me/leave-requests/{leave_a['id']}/withdraw", headers=me_b).status_code == 404
    assert (
        client.post(f"{BASE}/allocations/{alloc_a['id']}/cancel", json={"reason": "steal"}, headers=me_b).status_code
        == 404
    )
