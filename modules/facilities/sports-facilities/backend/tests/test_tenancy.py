"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak


def seed(org) -> dict:
    f = org.facility()
    s = org.space(f["id"])
    org.client.put(
        f"{BASE}/facilities/{f['id']}/hours",
        json={"slots": [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "10:00"}]},
        headers=org.admin,
    )
    u = org.usage(f["id"], "2026-10-26T06:00:00+05:30", "2026-10-26T07:00:00+05:30", space_id=s["id"])
    return {"facility": f, "space": s, "usage": u}


def test_no_cross_tenant_leak(client, org, other_org):
    a, b = seed(org), seed(other_org)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/facilities", "/usage"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(org.admin), token(other_org.admin))

    as_b = other_org.admin
    fa = a["facility"]["id"]
    for path in (
        f"/facilities/{fa}",
        f"/facilities/{fa}/spaces",
        f"/facilities/{fa}/hours",
        f"/facilities/{fa}/utilisation?from=2026-10-26&to=2026-10-26",
        f"/usage/{a['usage']['id']}",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    assert client.patch(f"{BASE}/facilities/{fa}", json={"name": "x"}, headers=as_b).status_code == 404
    assert client.put(f"{BASE}/facilities/{fa}/status", json={"status": "closed"}, headers=as_b).status_code == 404
    assert client.put(f"{BASE}/facilities/{fa}/hours", json={"slots": []}, headers=as_b).status_code == 404
    assert client.post(f"{BASE}/facilities/{fa}/spaces", json={"name": "x"}, headers=as_b).status_code == 404
    space_path = f"{BASE}/facilities/{fa}/spaces/{a['space']['id']}"
    assert client.patch(space_path, json={"active": False}, headers=as_b).status_code == 404
    # b's own facility with a's space is not found either
    cross_space = f"{BASE}/facilities/{b['facility']['id']}/spaces/{a['space']['id']}"
    assert client.patch(cross_space, json={"active": False}, headers=as_b).status_code == 404

    # another organisation's ids are unknown here, so they cannot be referenced
    steal = {"facility_id": fa, "used_from": "2026-10-26T06:00:00Z", "used_to": "2026-10-26T07:00:00Z"}
    r = client.post(f"{BASE}/usage", json={**steal, "purpose": "training"}, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_facility"
    mixed = {**steal, "facility_id": b["facility"]["id"], "space_id": a["space"]["id"], "purpose": "training"}
    r = client.post(f"{BASE}/usage", json=mixed, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "space_not_in_facility"
    # a's data is untouched and names are unique per organisation, not globally
    mine = client.get(f"{BASE}/facilities/{fa}", headers=org.admin).json()
    assert (mine["name"], mine["status"]) == (a["facility"]["name"], "operational")
    assert a["facility"]["name"] == b["facility"]["name"]
    assert client.get(f"{BASE}/usage?facility_id={fa}", headers=as_b).json() == {"items": [], "total": 0}
