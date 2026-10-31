"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak

MANAGER = "portfolio-manager"


def seed(client, org) -> tuple[str, dict, dict]:
    _, mgr = org.user(MANAGER)
    t = client.post(f"{BASE}/item-types", json={"name": "TypeA"}, headers=mgr).json()
    item = client.post(f"{BASE}/items", json={"type_id": t["id"], "title": "ItemOrg"}, headers=mgr).json()
    token = mgr["Authorization"].split(" ", 1)[1]
    return token, t, item


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, type_a, item_a = seed(client, org)
    token_b, type_b, item_b = seed(client, other_org)

    for path in ("/item-types", "/items?scope=mine", "/items?scope=managed"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)

    b_headers = {"Authorization": f"Bearer {token_b}"}
    assert client.get(f"{BASE}/item-types/{type_a['id']}", headers=b_headers).status_code in (404, 405)
    assert client.get(f"{BASE}/items/{item_a['id']}", headers=b_headers).status_code == 404
    assert (
        client.patch(
            f"{BASE}/items/{item_a['id']}", json={"type_id": type_a["id"], "title": "Hacked"}, headers=b_headers
        ).status_code
        == 404
    )
    assert client.delete(f"{BASE}/items/{item_a['id']}", headers=b_headers).status_code == 404
    assert client.post(f"{BASE}/items/{item_a['id']}/submit", headers=b_headers).status_code == 404
    assert client.post(f"{BASE}/items/{item_a['id']}/withdraw", headers=b_headers).status_code == 404

    # Cross-tenant item creation with other org's type_id should return 404 (type not found in org)
    cross = client.post(f"{BASE}/items", json={"type_id": type_a["id"], "title": "Cross Org"}, headers=b_headers)
    assert cross.status_code == 404
