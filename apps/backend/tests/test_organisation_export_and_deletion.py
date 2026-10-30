"""Issue #78: per-organisation export and deletion with retention, against the real host with every enabled module."""

from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal
from eos_core.rls import tenant_tables
from eos_core.tenant import platform_scope
from eos_tenancy.application import service as tenancy
from eos_tenancy.application import tables
from eos_testing import register_and_login
from eos_testing.tenancy import auth

SA = ("root@platform.example.com", "RootPassw0rd!")
BASE = "/api/v1/tenancy/admin/organisations"


def super_admin(client) -> dict:
    r = client.post("/api/v1/identity/auth/login", json={"email": SA[0], "password": SA[1]})
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


def rows_left(organisation_id: str) -> dict[str, int]:
    with SessionLocal() as db, platform_scope():
        every = [tables.organisation_row_table(), *tables.organisation_tables(db)]
        return {t.name: n for t in every if (n := tables.count_rows(db, t, organisation_id))}


def test_export_then_delete_restore_and_purge(client, monkeypatch):
    sa = super_admin(client)
    a = register_and_login(client, slug="dpdp-a", academy_type="music-academy")
    b = register_and_login(client, slug="dpdp-b", academy_type="law-college")
    for t in (a, b):
        up = client.post("/api/v1/billing/subscription/upgrade", json={"plan": "standard"}, headers=auth(t["token"]))
        assert up.status_code == 201, up.text
    a_id, b_id = a["org"]["id"], b["org"]["id"]

    # export: every tenant table of every enabled module is present, with only this organisation's rows
    r = client.get(f"{BASE}/{a_id}/export", headers=sa)
    assert r.status_code == 200, r.text
    assert 'filename="dpdp-a-export-' in r.headers["content-disposition"]
    doc = r.json()
    assert set(tenant_tables()) <= set(doc["tables"]) and "tenancy_organisation" in doc["tables"]
    assert len(doc["tables"]) > 20, "every enabled module's tables take part without code of their own"
    for name, rows in doc["tables"].items():
        for row in rows:
            assert row["id" if name == "tenancy_organisation" else "organisation_id"] == a_id, name
    assert doc["tables"]["identity_user"][0]["email"] == a["email"]
    assert doc["tables"]["identity_user"][0]["password_hash"] == "[redacted]"
    assert doc["tables"]["billing_invoice"][0]["status"] == "paid"
    assert b["email"] not in r.text and b_id not in r.text

    # org admins may not export or delete
    assert client.get(f"{BASE}/{a_id}/export", headers=auth(a["token"])).status_code == 403
    assert client.request("DELETE", f"{BASE}/{a_id}", headers=auth(a["token"])).status_code == 403

    # delete: paid invoices need the slug; archived users cannot sign in; module routes are refused
    assert client.request("DELETE", f"{BASE}/{a_id}", json={"reason": "left"}, headers=sa).status_code == 409
    r = client.request("DELETE", f"{BASE}/{a_id}", json={"reason": "left", "confirm_slug": "dpdp-a"}, headers=sa)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "archived" and r.json()["delete_after"]
    login = {"email": a["email"], "password": a["password"], "organisation_slug": "dpdp-a"}
    r = client.post("/api/v1/identity/auth/login", json=login)
    assert r.status_code == 401 and "archived" in r.json()["detail"]
    assert client.get("/api/v1/fees-accounts/ping", headers=auth(a["token"])).status_code == 403

    # restore while retention runs, then delete again
    assert client.post(f"{BASE}/{a_id}/restore", headers=sa).json()["status"] == "active"
    assert client.post("/api/v1/identity/auth/login", json=login).status_code == 200
    assert client.request("DELETE", f"{BASE}/{a_id}", json={"confirm_slug": "dpdp-a"}, headers=sa).status_code == 200

    # purge: refused before retention, complete after it, the other organisation untouched
    assert client.post(f"{BASE}/{a_id}/purge", headers=sa).status_code == 409
    before_b = rows_left(b_id)
    monkeypatch.setattr(tenancy, "clock", lambda: datetime.now(UTC) + timedelta(days=31))
    r = client.post(f"{BASE}/{a_id}/purge", headers=sa)
    assert r.status_code == 200, r.text
    assert r.json()["rows_deleted"]["identity_user"] == 1
    assert rows_left(a_id) == {}
    assert rows_left(b_id) == before_b
    assert client.get(f"{BASE}/{a_id}", headers=sa).status_code == 404
    assert client.get("/api/v1/tenancy/organisation", headers=auth(b["token"])).status_code == 200
