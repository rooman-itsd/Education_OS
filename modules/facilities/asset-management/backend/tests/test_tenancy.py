"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak

MANAGER = "asset-management-manager"
FINANCE = "asset-management-finance"


def seed(client, org) -> tuple[str, str, dict]:
    _, mgr = org.user(MANAGER)
    _, fin = org.user(FINANCE)
    cat = client.post(
        f"{BASE}/categories",
        json={"name": "IT", "depreciation": {"method": "straight_line", "useful_life_months": 36}},
        headers=mgr,
    ).json()
    asset = client.post(
        f"{BASE}/assets",
        json={
            "name": "Laptop",
            "category_id": cat["id"],
            "acquisition": {"date": "2026-08-01", "cost": {"amount": "36000", "currency": "INR"}},
        },
        headers=mgr,
    ).json()
    cycle = client.post(
        f"{BASE}/verification-cycles", json={"name": "Audit", "due_on": "2026-12-01"}, headers=mgr
    ).json()
    client.post(f"{BASE}/verification-cycles/{cycle['id']}/start", headers=mgr)
    run = client.post(f"{BASE}/depreciation-runs", json={"period_end": "2026-09-30"}, headers=fin).json()
    disposal = client.post(
        f"{BASE}/disposals", json={"asset_id": asset["id"], "method": "scrap", "reason": "x"}, headers=mgr
    ).json()
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    return token(mgr), token(fin), {"category": cat, "asset": asset, "cycle": cycle, "run": run, "disposal": disposal}


def test_no_cross_tenant_leak(client, org, other_org):
    mgr_a, fin_a, a = seed(client, org)
    mgr_b, fin_b, b = seed(client, other_org)
    for path in ("/categories", "/assets", "/verification-cycles"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", mgr_a, mgr_b)
    for path in ("/depreciation-runs", "/disposals"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", fin_a, fin_b)
    as_b = {"Authorization": f"Bearer {mgr_b}"}
    # /verifications/due rows carry no organisation_id (contract), so compare the assets and cycles it returns
    due_b = client.get(f"{BASE}/verifications/due?within_days=3650", headers=as_b).json()
    assert a["asset"]["id"] not in [x["asset_id"] for x in due_b["assets"]]
    assert [c["id"] for c in due_b["open_cycles"]] == [b["cycle"]["id"]]
    fin_as_b = {"Authorization": f"Bearer {fin_b}"}
    assert client.get(f"{BASE}/assets/{a['asset']['id']}", headers=as_b).status_code == 404
    assert client.get(f"{BASE}/assets/{a['asset']['id']}/transfers", headers=as_b).status_code == 404
    assert client.patch(f"{BASE}/assets/{a['asset']['id']}", json={"make": "x"}, headers=as_b).status_code == 404
    assert client.patch(f"{BASE}/categories/{a['category']['id']}", json={"name": "y"}, headers=as_b).status_code == 404
    assert client.get(f"{BASE}/verification-cycles/{a['cycle']['id']}/lines", headers=as_b).status_code == 404
    assert client.post(f"{BASE}/depreciation-runs/{a['run']['id']}/post", headers=fin_as_b).status_code == 404
    assert client.post(f"{BASE}/disposals/{a['disposal']['id']}/approve", headers=fin_as_b).status_code == 404
    steal = client.post(f"{BASE}/assets", json={"name": "x", "category_id": a["category"]["id"]}, headers=as_b)
    assert steal.status_code == 422  # another organisation's category is unknown here
    assert b["asset"]["organisation_id"] == other_org.id
    assert a["asset"]["tag"] == b["asset"]["tag"]  # tags are numbered per organisation
    totals = client.get(f"{BASE}/summary", headers=fin_as_b).json()
    assert totals["assets_total"] == 1
