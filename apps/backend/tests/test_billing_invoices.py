"""Invoices: an activated paid period leaves one paid invoice the organisation can list, and nobody else can."""

from eos_testing import assert_no_cross_tenant_leak, register_and_login
from eos_testing.tenancy import auth


def test_an_upgrade_writes_one_paid_invoice_for_the_period(client):
    a = register_and_login(client, slug="invoice-one", academy_type="music-academy")
    h = auth(a["token"])
    assert client.get("/api/v1/billing/invoices", headers=h).json() == []  # a trial charges nothing
    up = client.post("/api/v1/billing/subscription/upgrade", json={"plan": "standard"}, headers=h)
    assert up.status_code == 201 and up.json()["activated"] is True
    invoices = client.get("/api/v1/billing/invoices", headers=h).json()
    assert len(invoices) == 1
    inv = invoices[0]
    assert inv["plan"] == "standard" and inv["status"] == "paid" and inv["currency"] == "INR"
    assert inv["amount"] == 24999 and inv["payment_reference"] == up.json()["reference"]
    assert inv["period_start"] < inv["period_end"] and inv["organisation_id"] == a["org"]["id"]
    # a yearly cycle charges twelve months in one invoice
    up = client.post(
        "/api/v1/billing/subscription/upgrade", json={"plan": "premium", "billing_cycle": "yearly"}, headers=h
    )
    assert up.status_code == 201
    newest = client.get("/api/v1/billing/invoices", headers=h).json()[0]
    assert (
        newest["plan"] == "premium"
        and newest["amount"] == 12 * client.get("/api/v1/billing/plans").json()[-1]["price_per_month"]
    )


def test_invoices_are_scoped_to_the_organisation(client):
    a = register_and_login(client, slug="invoice-a")
    b = register_and_login(client, slug="invoice-b", academy_type="law-college")
    for t in (a, b):
        client.post("/api/v1/billing/subscription/upgrade", json={"plan": "standard"}, headers=auth(t["token"]))
    assert_no_cross_tenant_leak(client, "/api/v1/billing/invoices", a["token"], b["token"])
    assert client.get("/api/v1/billing/invoices").status_code == 401
