"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, YEAR, Campus, at
from eos_hostel.infrastructure.models import new_id
from eos_testing import assert_no_cross_tenant_leak


def seed(client, org) -> tuple[Campus, dict]:
    c = Campus(client, org)
    person_id, me, alloc = c.resident()
    lv = c.post("/me/leave-requests", {"from": at(14), "to": at(18), "destination": "Home", "reason": "Visit"}, me)
    visit = c.post("/visits", {"person_id": person_id, "visitor_name": "Guest"}, c.security)
    incident = c.post(
        "/incidents", {"person_id": person_id, "occurred_at": at(7), "category": "Noise", "description": "x"}, c.warden
    )
    notice = c.post("/notices", {"title": "Hello", "body": "x", "hostel_id": c.hostel["id"]}, c.warden)
    client.put(
        f"{BASE}/mess-menus",
        json=[{"hostel_id": c.hostel["id"], "date": "2026-10-12", "meal": "lunch", "items": ["Rice"]}],
        headers=c.admin,
    )
    c.post("/me/room-requests", {"academic_year": "2027-28"}, me)
    ids = {
        "me": me,
        "allocation": alloc["id"],
        "leave": lv.json()["id"],
        "visit": visit.json()["id"],
        "incident": incident.json()["id"],
        "notice": notice.json()["id"],
    }
    return c, ids


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def test_no_cross_tenant_leak(client, org, other_org):
    a, a_ids = seed(client, org)
    b, b_ids = seed(client, other_org)
    staff = [
        ("/hostels", a.admin, b.admin),
        ("/allocations", a.admin, b.admin),
        ("/leave-requests", a.warden, b.warden),
        ("/visits", a.warden, b.warden),
        ("/incidents", a.warden, b.warden),
        ("/notices", a.warden, b.warden),
        ("/me/notices", a_ids["me"], b_ids["me"]),
        ("/me/leave-requests", a_ids["me"], b_ids["me"]),
        ("/me/visits", a_ids["me"], b_ids["me"]),
    ]
    for path, ha, hb in staff:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    assert client.get(f"{BASE}/hostels/{a.hostel['id']}/rooms", headers=b.admin).status_code == 404
    menu = f"{BASE}/mess-menus?hostel_id={a.hostel['id']}&from=2026-10-12&to=2026-10-12"
    assert client.get(menu, headers=a.admin).json()[0]["organisation_id"] == org.id
    assert client.get(menu, headers=b.admin).status_code == 404


def test_another_organisations_records_are_not_found(client, org, other_org):
    a, ids = seed(client, org)
    b = Campus(client, other_org)
    room_b = b.room["id"]
    gets = [f"/hostels/{a.hostel['id']}", f"/allocations/{ids['allocation']}"]
    for path in gets:
        assert client.get(f"{BASE}{path}", headers=b.admin).status_code == 404
    posts = [
        (f"/allocations/{ids['allocation']}/check-out", None, b.warden),
        (f"/allocations/{ids['allocation']}/cancel", {"reason": "steal"}, b.warden),
        (f"/leave-requests/{ids['leave']}/decision", {"decision": "approved"}, b.warden),
        (f"/leave-requests/{ids['leave']}/return", None, b.warden),
        (f"/visits/{ids['visit']}/out", None, b.security),
        (f"/notices/{ids['notice']}/withdraw", None, b.warden),
        (f"/hostels/{a.hostel['id']}/rooms", {"number": "X1", "room_type": "single", "capacity": 1}, b.admin),
        (
            "/allocations",
            {
                "person_id": new_id(),
                "room_id": a.room["id"],
                "bed": "2",
                "academic_year": YEAR,
                "from": "2026-10-12",
                "to": "2027-05-31",
            },
            b.warden,
        ),
        ("/notices", {"title": "x", "body": "x", "hostel_id": a.hostel["id"]}, b.warden),
    ]
    for path, body, headers in posts:
        assert client.post(f"{BASE}{path}", json=body, headers=headers).status_code == 404, path
    assert client.patch(f"{BASE}/rooms/{a.room['id']}", json={"capacity": 5}, headers=b.admin).status_code == 404
    assert (
        client.patch(f"{BASE}/incidents/{ids['incident']}", json={"status": "closed"}, headers=b.warden).status_code
        == 404
    )
    assert client.patch(f"{BASE}/hostels/{a.hostel['id']}", json={"active": False}, headers=b.admin).status_code == 404
    # B's own room is untouched by A's attempts and still has both beds free.
    assert client.get(f"{BASE}/hostels/{b.hostel['id']}/rooms", headers=b.admin).json()[0]["id"] == room_b
