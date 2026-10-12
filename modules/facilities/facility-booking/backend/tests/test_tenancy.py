"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE, at
from eos_testing import assert_no_cross_tenant_leak

MANAGER = "facility-booking-manager"


def seed(client, org) -> tuple[str, dict, dict]:
    _, mgr = org.user(MANAGER)
    t = client.post(f"{BASE}/resource-types", json={"name": "Room"}, headers=mgr).json()
    room = client.post(f"{BASE}/resources", json={"name": "Room", "type_id": t["id"]}, headers=mgr).json()
    booking = client.post(
        f"{BASE}/bookings", json={"resource_id": room["id"], "start_at": at(9), "end_at": at(10)}, headers=mgr
    ).json()["booking"]
    return mgr["Authorization"].split(" ", 1)[1], room, booking


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, room_a, booking_a = seed(client, org)
    token_b, room_b, _ = seed(client, other_org)
    for path in ("/resource-types", "/resources", "/bookings?scope=managed&from=now", "/bookings?scope=mine&from=now"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)
    b_headers = {"Authorization": f"Bearer {token_b}"}
    assert client.get(f"{BASE}/resources/{room_a['id']}", headers=b_headers).status_code == 404
    assert client.get(f"{BASE}/bookings/{booking_a['id']}", headers=b_headers).status_code == 404
    assert (
        client.post(f"{BASE}/bookings/{booking_a['id']}/cancel", json={"reason": "x"}, headers=b_headers).status_code
        == 404
    )
    cross = client.post(
        f"{BASE}/bookings", json={"resource_id": room_a["id"], "start_at": at(11), "end_at": at(12)}, headers=b_headers
    )
    assert cross.status_code == 404
    assert room_b["organisation_id"] == other_org.id
