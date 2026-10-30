"""Vendors: registration, the masked bank account, approval, suspension and blacklisting (F1-F3)."""

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_procurement.infrastructure.models import Vendor
from pc_support import BASE, outbox, vendor
from sqlalchemy import select


def test_register_keeps_only_the_last_four_digits(client, org):
    body = {
        "name": "Acme Scientific",
        "categories": ["lab equipment", "IT"],
        "email": "sales@acme.example.com",
        "gstin": "29abcde1234f1z5",
        "pan": "abcde1234f",
        "bank_account": {"account_number": "123456789012", "ifsc": "sbin0001234"},
    }
    r = client.post(f"{BASE}/vendors", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "pending" and v["organisation_id"] == org.id
    assert v["gstin"] == "29ABCDE1234F1Z5" and v["pan"] == "ABCDE1234F"
    assert v["bank_account"] == {"account_last4": "9012", "ifsc": "SBIN0001234"}
    assert "123456789012" not in r.text
    with SessionLocal() as db, platform_scope():
        row = db.scalar(select(Vendor).where(Vendor.id == v["id"]))
        stored = " ".join(str(getattr(row, c.name)) for c in Vendor.__table__.columns)
    assert "123456789012" not in stored and row.bank_account_last4 == "9012"
    # an edit that sends no new number keeps the last four digits
    body["bank_account"] = {"ifsc": "SBIN0009999"}
    r = client.put(f"{BASE}/vendors/{v['id']}", json=body, headers=org.staff)
    assert r.status_code == 200 and r.json()["bank_account"] == {"account_last4": "9012", "ifsc": "SBIN0009999"}


def test_gstin_and_pan_are_unique_in_the_organisation(client, org, other_org):
    vendor(client, org, approved=False, gstin="29ABCDE1234F1Z5", pan="ABCDE1234F")
    dup = {"name": "Copy", "categories": ["IT"], "gstin": "29abcde1234f1z5"}
    r = client.post(f"{BASE}/vendors", json=dup, headers=org.staff)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "vendor_exists"
    r = client.post(
        f"{BASE}/vendors", json={"name": "Copy", "categories": ["IT"], "pan": "ABCDE1234F"}, headers=org.staff
    )
    assert r.status_code == 409
    assert client.post(f"{BASE}/vendors", json=dup, headers=other_org.staff).status_code == 201


def test_status_changes_need_a_reason_and_blacklisting_is_published(client, org):
    v = vendor(client, org, approved=False)
    url = f"{BASE}/vendors/{v['id']}/status"
    assert client.post(url, json={"status": "approved", "reason": ""}, headers=org.staff).status_code == 422
    assert client.post(url, json={"status": "pending", "reason": "x"}, headers=org.staff).status_code == 422
    assert (
        client.post(url, json={"status": "approved", "reason": "documents checked"}, headers=org.staff).json()["status"]
        == "approved"
    )
    r = client.post(url, json={"status": "approved", "reason": "again"}, headers=org.staff)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "status_unchanged"
    r = client.post(url, json={"status": "suspended", "reason": "late deliveries"}, headers=org.staff)
    assert r.json()["status"] == "suspended" and r.json()["status_reason"] == "late deliveries"
    r = client.post(url, json={"status": "blacklisted", "reason": "fake invoices"}, headers=org.staff)
    assert r.json()["status"] == "blacklisted"
    events = [e for e in outbox("procurement.vendor.blacklisted", org.id) if e["vendor_id"] == v["id"]]
    assert events == [{"organisation_id": org.id, "vendor_id": v["id"], "reason": "fake invoices"}]


def test_list_filters_and_permissions(client, org):
    lab = vendor(client, org, categories=["Lab Equipment"])
    it = vendor(client, org, approved=False, categories=["IT"], name="Zeta Computers")
    ids = lambda r: {v["id"] for v in r.json()["items"]}  # noqa: E731
    assert lab["id"] in ids(client.get(f"{BASE}/vendors?category=lab%20equipment", headers=org.staff))
    assert it["id"] not in ids(client.get(f"{BASE}/vendors?category=lab%20equipment", headers=org.staff))
    assert ids(client.get(f"{BASE}/vendors?q=zeta", headers=org.manager)) == {it["id"]}
    assert it["id"] in ids(client.get(f"{BASE}/vendors?status=pending", headers=org.admin))
    page = client.get(f"{BASE}/vendors?limit=1", headers=org.staff).json()
    assert len(page["items"]) == 1 and page["next_cursor"] == "1"
    assert client.get(f"{BASE}/vendors", headers=org.faculty).status_code == 403
    assert (
        client.post(f"{BASE}/vendors", json={"name": "x", "categories": ["IT"]}, headers=org.manager).status_code == 403
    )
    assert client.get(f"{BASE}/vendors", headers={}).status_code == 401
    assert client.post(f"{BASE}/vendors", json={"name": "x", "categories": []}, headers=org.staff).status_code == 422
    r = client.post(f"{BASE}/vendors", json={"name": "x", "categories": ["IT"], "colour": "red"}, headers=org.staff)
    assert r.status_code == 422  # unknown fields are refused
    r = client.post(
        f"{BASE}/vendors",
        json={"name": "x", "categories": ["IT"], "bank_account": {"account_number": "12AB"}},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_account_number"
