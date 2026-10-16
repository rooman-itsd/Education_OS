"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from datetime import timedelta

from conftest import BASE, NOW
from eos_testing import assert_no_cross_tenant_leak

MANAGER = "inventory-equipment-manager"


def seed(client, org) -> tuple[str, dict, dict]:
    _, mgr = org.user(MANAGER)
    cat = client.post(f"{BASE}/categories", json={"name": "Equipment"}, headers=mgr).json()
    loc = client.post(f"{BASE}/locations", json={"name": "Store"}, headers=mgr).json()
    item = client.post(
        f"{BASE}/items", json={"name": "Cable", "category_id": cat["id"], "tracking": "quantity"}, headers=mgr
    ).json()
    client.post(
        f"{BASE}/movements",
        json={"kind": "receipt", "item_id": item["id"], "quantity": 5, "to_location_id": loc["id"]},
        headers=mgr,
    )
    loan = client.post(
        f"{BASE}/loans",
        json={"lines": [{"item_id": item["id"]}], "due_at": (NOW + timedelta(days=2)).isoformat()},
        headers=mgr,
    ).json()
    return mgr["Authorization"].split(" ", 1)[1], item, loan


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, item_a, loan_a = seed(client, org)
    token_b, item_b, _ = seed(client, other_org)
    for path in ("/categories", "/locations", "/items", "/movements", "/loans?scope=managed", "/loans?scope=mine"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)
    b = {"Authorization": f"Bearer {token_b}"}
    assert client.get(f"{BASE}/items/{item_a['id']}", headers=b).status_code == 404
    assert client.get(f"{BASE}/loans/{loan_a['id']}", headers=b).status_code == 404
    assert client.post(f"{BASE}/loans/{loan_a['id']}/cancel", headers=b).status_code == 404
    steal = client.post(
        f"{BASE}/movements",
        json={"kind": "issue", "item_id": item_a["id"], "quantity": 1, "from_location_id": "x"},
        headers=b,
    )
    assert steal.status_code == 404
    borrow = client.post(
        f"{BASE}/loans",
        json={"lines": [{"item_id": item_a["id"]}], "due_at": (NOW + timedelta(days=2)).isoformat()},
        headers=b,
    )
    assert borrow.status_code == 404
    assert item_b["organisation_id"] == other_org.id
