"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak

MANAGER = "maintenance-manager"


def seed(client, org) -> tuple[str, dict, dict, dict]:
    _, mgr = org.user(MANAGER)
    cat = client.post(f"{BASE}/categories", json={"name": "Electrical"}, headers=mgr).json()
    target = {"kind": "location", "label": "Main hall"}
    ticket = client.post(
        f"{BASE}/tickets", json={"title": "Light out", "category_id": cat["id"], "target": target}, headers=mgr
    ).json()["ticket"]
    schedule = client.post(
        f"{BASE}/schedules",
        json={
            "title": "Check lights",
            "category_id": cat["id"],
            "target": target,
            "every": 1,
            "unit": "months",
            "next_due_on": "2026-12-01",
        },
        headers=mgr,
    ).json()
    return mgr["Authorization"].split(" ", 1)[1], cat, ticket, schedule


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, cat_a, ticket_a, schedule_a = seed(client, org)
    token_b, _, ticket_b, _ = seed(client, other_org)
    for path in ("/categories", "/tickets?scope=managed", "/tickets?scope=mine", "/schedules"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)
    b = {"Authorization": f"Bearer {token_b}"}
    assert client.get(f"{BASE}/tickets/{ticket_a['id']}", headers=b).status_code == 404
    assert client.get(f"{BASE}/tickets/{ticket_a['id']}/work-entries", headers=b).status_code == 404
    assert client.post(f"{BASE}/tickets/{ticket_a['id']}/cancel", json={"reason": "x"}, headers=b).status_code == 404
    assert client.patch(f"{BASE}/categories/{cat_a['id']}", json={"name": "Mine"}, headers=b).status_code == 404
    assert client.get(f"{BASE}/schedules/{schedule_a['id']}", headers=b).status_code == 404
    assert client.post(f"{BASE}/schedules/{schedule_a['id']}/raise-now", headers=b).status_code == 404
    borrow = client.post(
        f"{BASE}/tickets",
        json={"title": "x", "category_id": cat_a["id"], "target": {"kind": "location", "label": "y"}},
        headers=b,
    )
    assert borrow.status_code == 422  # another organisation's category is unknown here
    summary_b = client.get(f"{BASE}/summary", headers=b).json()
    assert summary_b["open"] == 1
    assert ticket_b["organisation_id"] == other_org.id
    assert ticket_a["number"] == ticket_b["number"]  # numbering is per organisation
