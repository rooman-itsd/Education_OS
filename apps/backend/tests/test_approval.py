"""Super admin approval of an organisation's academic package (ADR-0005)."""

import pytest
from eos_tenancy.application import service as tenancy
from eos_testing import register_and_login
from eos_testing.tenancy import auth

SA = ("root@platform.example.com", "RootPassw0rd!")


@pytest.fixture
def manual_approval(monkeypatch):
    monkeypatch.setattr(tenancy, "AUTO_APPROVE", False)


def test_package_needs_super_admin_approval(client, manual_approval):
    r = client.post(
        "/api/v1/tenancy/register",
        json={
            "organisation_name": "Pending College",
            "slug": "pending-college",
            "academy_type": "law-college",
            "admin": {"name": "A", "email": "admin@pending.example.com", "password": "Passw0rd!x"},
            "accepted_terms": True,
        },
    )
    assert r.status_code == 201
    token = r.json()["verification_token"]
    v = client.post("/api/v1/tenancy/register/verify", json={"token": token})
    assert v.status_code == 200 and v.json()["status"] == "pending_approval"
    # cannot sign in yet
    r = client.post(
        "/api/v1/identity/auth/login", json={"email": "admin@pending.example.com", "password": "Passw0rd!x"}
    )
    assert r.status_code == 401 and "pending_approval" in r.json()["detail"]
    # super admin sees it in the queue and approves
    sa = auth(client.post("/api/v1/identity/auth/login", json={"email": SA[0], "password": SA[1]}).json()["token"])
    queue = client.get("/api/v1/tenancy/admin/organisations?status=pending_approval", headers=sa).json()
    assert any(o["slug"] == "pending-college" for o in queue)
    a = client.post(
        f"/api/v1/tenancy/admin/organisations/{v.json()['id']}/approve",
        json={"reason": "verified institution"},
        headers=sa,
    )
    assert a.status_code == 200 and a.json()["status"] == "active"
    from eos_core import notify

    approval_emails = [
        m for m in notify.sent if m["to"] == "admin@pending.example.com" and "approved" in m["subject"].lower()
    ]
    assert len(approval_emails) == 1
    assert approval_emails[0]["organisation_id"] == v.json()["id"]
    assert "Pending College" in approval_emails[0]["subject"]
    assert "law-college" in approval_emails[0]["body"]

    assert (
        client.post(
            "/api/v1/identity/auth/login", json={"email": "admin@pending.example.com", "password": "Passw0rd!x"}
        ).status_code
        == 200
    )
    # approving twice is a no-op error, not a silent success
    assert (
        client.post(f"/api/v1/tenancy/admin/organisations/{v.json()['id']}/approve", json={}, headers=sa).status_code
        == 409
    )


def test_package_rejection_sends_email(client, manual_approval):
    from eos_core import notify

    r = client.post(
        "/api/v1/tenancy/register",
        json={
            "organisation_name": "Rejected College",
            "slug": "rejected-college",
            "academy_type": "sports-college",
            "admin": {"name": "R", "email": "admin@rejected.example.com", "password": "Passw0rd!x"},
            "accepted_terms": True,
        },
    )
    assert r.status_code == 201
    token = r.json()["verification_token"]
    v = client.post("/api/v1/tenancy/register/verify", json={"token": token})
    assert v.status_code == 200 and v.json()["status"] == "pending_approval"

    sa = auth(client.post("/api/v1/identity/auth/login", json={"email": SA[0], "password": SA[1]}).json()["token"])
    rej = client.post(
        f"/api/v1/tenancy/admin/organisations/{v.json()['id']}/reject",
        json={"reason": "Incomplete documentation"},
        headers=sa,
    )
    assert rej.status_code == 200 and rej.json()["status"] == "suspended"

    # cannot sign in
    r = client.post(
        "/api/v1/identity/auth/login", json={"email": "admin@rejected.example.com", "password": "Passw0rd!x"}
    )
    assert r.status_code == 401 and "suspended" in r.json()["detail"]

    # rejection email was sent
    rejection_emails = [
        m for m in notify.sent if m["to"] == "admin@rejected.example.com" and "not approved" in m["subject"].lower()
    ]
    assert len(rejection_emails) == 1
    assert "Incomplete documentation" in rejection_emails[0]["body"]

    # rejecting again fails with 409
    assert (
        client.post(
            f"/api/v1/tenancy/admin/organisations/{v.json()['id']}/reject",
            json={"reason": "again"},
            headers=sa,
        ).status_code
        == 409
    )


def test_package_change_takes_effect_only_after_approval(client, manual_approval):
    a = register_and_login(client, slug="switching-academy", academy_type="music-academy", super_admin=SA)
    h = auth(a["token"])
    r = client.put("/api/v1/tenancy/organisation/academy-package", json={"academy_type": "dance-academy"}, headers=h)
    assert (
        r.status_code == 200
        and r.json()["requested_academy_type"] == "dance-academy"
        and r.json()["academy_type"] == "music-academy"
    )
    assert client.get("/api/v1/tenancy/organisation/entitlement", headers=h).json()["academy_type"] == "music-academy"
    sa = auth(client.post("/api/v1/identity/auth/login", json={"email": SA[0], "password": SA[1]}).json()["token"])
    r = client.post(f"/api/v1/tenancy/admin/organisations/{a['org']['id']}/approve", json={"reason": "ok"}, headers=sa)
    assert (
        r.status_code == 200
        and r.json()["academy_type"] == "dance-academy"
        and r.json()["requested_academy_type"] is None
    )
    assert client.get("/api/v1/tenancy/organisation/entitlement", headers=h).json()["academy_type"] == "dance-academy"
    assert (
        client.put("/api/v1/tenancy/organisation/academy-package", json={"academy_type": "nope"}, headers=h).status_code
        == 400
    )
