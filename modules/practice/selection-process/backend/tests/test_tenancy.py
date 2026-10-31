"""Cross-tenant leak test: one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak

COORDINATOR = "selection-process-coordinator"


def seed(client, org) -> tuple[str, dict, dict]:
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": f"Type-{org.id[:6]}"}, headers=coord).json()
    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": f"Process-{org.id[:6]}",
            "stages": [{"name": "Stage 1", "sequence": 1}],
        },
        headers=coord,
    ).json()
    token = coord["Authorization"].split(" ", 1)[1]
    return token, t, p


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, type_a, proc_a = seed(client, org)
    token_b, type_b, proc_b = seed(client, other_org)

    for path in ("/process-types", "/processes"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)

    b_headers = {"Authorization": f"Bearer {token_b}"}
    assert client.get(f"{BASE}/process-types/{type_a['id']}", headers=b_headers).status_code in (404, 405)
    assert client.get(f"{BASE}/processes/{proc_a['id']}", headers=b_headers).status_code == 404
    assert (
        client.patch(f"{BASE}/processes/{proc_a['id']}", json={"title": "Hacked"}, headers=b_headers).status_code == 404
    )
    assert client.delete(f"{BASE}/processes/{proc_a['id']}", headers=b_headers).status_code == 404

    # Cross-tenant process creation with other org's type_id should return 404
    cross = client.post(
        f"{BASE}/processes",
        json={"type_id": type_a["id"], "title": "Cross Org"},
        headers=b_headers,
    )
    assert cross.status_code == 404
