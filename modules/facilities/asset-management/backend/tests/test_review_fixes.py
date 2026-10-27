"""Regressions found in review of the module PR: an acquisition patch must keep the cost, transfers refuse
explicit nulls, depreciation and disposals stay in the past, and straight-line ends with the useful life."""

from datetime import date
from decimal import Decimal

from conftest import BASE
from eos_asset_management.domain.rules import Depreciation, project

MANAGER = "asset-management-manager"
FINANCE = "asset-management-finance"
STRAIGHT_LINE = {"method": "straight_line", "useful_life_months": 60, "residual_percent": 5}


def inr(amount: str) -> dict:
    return {"amount": amount, "currency": "INR"}


def _asset(client, org):
    _, mgr = org.user(MANAGER)
    _, fin = org.user(FINANCE)
    cat = client.post(
        f"{BASE}/categories", json={"name": "IT", "code": "IT", "depreciation": STRAIGHT_LINE}, headers=mgr
    ).json()
    created = client.post(
        f"{BASE}/assets",
        json={
            "name": "Laptop",
            "category_id": cat["id"],
            "acquisition": {"date": "2026-01-01", "cost": inr("60000.00"), "supplier_name": "Acme"},
        },
        headers=mgr,
    )
    assert created.status_code == 201, created.text
    return mgr, fin, created.json()


def test_acquisition_patch_keeps_the_cost_and_cannot_undercut_depreciation(client, org):
    mgr, fin, a = _asset(client, org)
    r = client.patch(f"{BASE}/assets/{a['id']}", json={"acquisition": {"supplier_name": "New"}}, headers=mgr)
    assert r.status_code == 200, r.text
    assert r.json()["acquisition"]["cost"]["amount"] == "60000.00"
    assert r.json()["acquisition"]["supplier_name"] == "New"
    assert r.json()["acquisition"]["date"] == "2026-01-01"

    run = client.post(f"{BASE}/depreciation-runs", json={"period_end": "2026-09-30"}, headers=fin).json()
    assert client.post(f"{BASE}/depreciation-runs/{run['id']}/post", headers=fin).status_code == 200
    r = client.patch(f"{BASE}/assets/{a['id']}", json={"acquisition": {"cost": inr("1000.00")}}, headers=mgr)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "cost_below_depreciation"
    book = Decimal(client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()["book_value"]["amount"])
    assert book > 0


def test_transfer_refuses_explicit_null_fields(client, org):
    mgr, _, a = _asset(client, org)
    assert (
        client.post(
            f"{BASE}/assets/{a['id']}/transfers", json={"location": "Lab 1", "reason": "move"}, headers=mgr
        ).status_code
        == 201
    )
    r = client.post(f"{BASE}/assets/{a['id']}/transfers", json={"location": None, "reason": "x"}, headers=mgr)
    assert r.status_code == 422
    assert client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()["location"] == "Lab 1"


def test_depreciation_and_disposal_cannot_be_in_the_future(client, org):
    mgr, fin, a = _asset(client, org)
    r = client.post(f"{BASE}/depreciation-runs", json={"period_end": "2028-12-31"}, headers=fin)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "period_in_future"

    d = client.post(f"{BASE}/disposals", json={"asset_id": a["id"], "method": "sale", "reason": "old"}, headers=mgr)
    assert d.status_code == 201, d.text
    assert client.post(f"{BASE}/disposals/{d.json()['id']}/approve", headers=fin).status_code == 200
    r = client.post(
        f"{BASE}/disposals/{d.json()['id']}/complete",
        json={"disposed_on": "2029-06-30", "proceeds": inr("100.00")},
        headers=mgr,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"


def test_straight_line_schedule_ends_with_the_useful_life():
    d = Depreciation(method="straight_line", useful_life_months=3, residual_percent=0)
    steps = project(d, Decimal("100"), Decimal("100"), date(2026, 1, 1), None)
    assert len(steps) == 3
    assert sum(amount for _, amount, _ in steps) == Decimal("100.00")
    assert steps[-1][2] == Decimal("0.00")
