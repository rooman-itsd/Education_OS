"""Audit is fed by the outbox, end to end with the installed modules (#317 follow-up).

A super admin approves a registration and then impersonates its admin. Tenancy publishes the events, event-bus's
relay hands them to audit's consumer (found on its `eos.event_consumers` entry point), and the records appear in
the organisation's own audit trail and, for the super admin operations, at platform level: what the
`audit.super-admin-actions` widget reads. Before, nothing called audit, so both were empty."""

import uuid

import pytest
from eos_event_bus.application.consumers import discover as discover_consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_tenancy.application import service as tenancy
from eos_testing.tenancy import auth

SA = ("root@platform.example.com", "RootPassw0rd!")


@pytest.fixture
def manual_approval(monkeypatch):
    monkeypatch.setattr(tenancy, "AUTO_APPROVE", False)


def _drain() -> None:
    relay = Relay(InProcessTransport(discover_consumers()), EventBusConfig())
    for _ in range(30):
        if relay.run_once().claimed == 0:
            return
    raise AssertionError("the outbox did not drain")


def test_super_admin_operations_reach_the_audit_trail(client, manual_approval):
    slug = f"audited-{uuid.uuid4().hex[:8]}"
    email = f"admin@{slug}.example.com"
    r = client.post(
        "/api/v1/tenancy/register",
        json={
            "organisation_name": "Audited College",
            "slug": slug,
            "academy_type": "law-college",
            "admin": {"name": "A", "email": email, "password": "Passw0rd!x"},
            "accepted_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    org_id = client.post("/api/v1/tenancy/register/verify", json={"token": r.json()["verification_token"]}).json()["id"]
    sa_login = client.post("/api/v1/identity/auth/login", json={"email": SA[0], "password": SA[1]}).json()
    sa = auth(sa_login["token"])
    assert client.post(f"/api/v1/tenancy/admin/organisations/{org_id}/approve", json={}, headers=sa).status_code == 200
    admin_login = client.post("/api/v1/identity/auth/login", json={"email": email, "password": "Passw0rd!x"}).json()
    admin_id = admin_login["user"]["id"]
    imp = client.post(
        f"/api/v1/tenancy/admin/organisations/{org_id}/impersonate",
        json={"user_id": admin_id, "reason": "support ticket 42"},
        headers=sa,
    )
    assert imp.status_code == 201, imp.text

    _drain()
    _drain()  # redelivery-safe: a second pass records nothing twice

    # The organisation's admin sees its own trail
    org_admin = auth(admin_login["token"])
    trail = client.get("/api/v1/audit/records?limit=200", headers=org_admin)
    assert trail.status_code == 200, trail.text
    actions = [r["action"] for r in trail.json()["items"]]
    for expected in ("organisation.registered", "organisation.verified", "organisation.approved"):
        assert actions.count(expected) == 1, (expected, actions)
    assert actions.count("impersonation.started") == 1

    # The super admin's platform-level view: the operations a super admin performed, once each
    platform = client.get("/api/v1/audit/records?limit=200", headers=sa)
    assert platform.status_code == 200, platform.text
    mine = [r for r in platform.json()["items"] if (r.get("context") or {}).get("organisation_id") == org_id]
    assert sorted(r["action"] for r in mine) == ["impersonation.started", "organisation.approved"]
    impersonation = next(r for r in mine if r["action"] == "impersonation.started")
    assert impersonation["actor"] == sa_login["user"]["id"]
    assert impersonation["entity_id"] == admin_id
