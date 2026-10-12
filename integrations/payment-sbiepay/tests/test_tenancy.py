"""No organisation sees another's payments, runs or merchant account (module standard: cross-tenant leak test)."""

from datetime import date

from eos_testing import assert_no_cross_tenant_leak
from sbiepay_support import PREFIX, browser_pays, start


def test_no_cross_tenant_leak(client, org, other_org):
    for o in (org, other_org):
        client.put(
            f"{PREFIX}/merchant-account", json={"merchant_id": f"M-{o.id[:8]}", "mode": "sandbox"}, headers=o.admin
        )
        browser_pays(client, start(client, o.admin))
        client.post(
            f"{PREFIX}/reconciliation/runs", json={"settlement_date": date.today().isoformat()}, headers=o.staff
        )

    assert_no_cross_tenant_leak(client, f"{PREFIX}/payments", org.token("admin"), other_org.token("admin"))
    assert_no_cross_tenant_leak(client, f"{PREFIX}/reconciliation/runs", org.token("staff"), other_org.token("staff"))


def test_another_organisations_payment_is_not_found(client, org, other_org):
    s = start(client, org.admin)
    for path in (f"/payments/{s['reference']}", f"/payments/{s['reference']}/verify"):
        method = client.get if path.endswith(s["reference"]) else client.post
        headers = other_org.admin if method is client.get else other_org.staff
        assert method(f"{PREFIX}{path}", headers=headers).status_code == 404
    r = client.post(
        f"{PREFIX}/payments/{s['reference']}/refunds", json={"amount": "1", "reason": "x"}, headers=other_org.staff
    )
    assert r.status_code == 404


def test_same_source_reference_in_two_organisations_is_two_payments(client, org, other_org):
    a = start(client, org.admin, source_reference="invoice-1")
    b = start(client, other_org.admin, source_reference="invoice-1")
    assert a["reference"] != b["reference"]


def test_merchant_accounts_are_per_organisation(client, org, other_org):
    client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "ONLY-A", "mode": "sandbox"}, headers=org.admin)
    r = client.get(f"{PREFIX}/merchant-account", headers=other_org.admin)
    assert r.status_code == 404 or r.json()["merchant_id"] != "ONLY-A"
