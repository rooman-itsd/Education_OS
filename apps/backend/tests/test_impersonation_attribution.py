"""Security review N3 (#672): what a super admin does while impersonating is attributed to the super admin too.

The impersonation token names the organisation user (`sub`, whose permissions apply) and the super admin (`imp`).
Before, only `tenancy.impersonation.started` named the super admin: every later event, and the audit record made
from it, carried the impersonated user alone. Now the host puts `imp` into the request context
(eos_backend.actor), eos_core.events.publish() copies it onto the envelope's `impersonated_by`, and audit records
it as `context.impersonated_by`. The actor and the permissions stay the impersonated user's."""

import uuid

from eos_backend.main import create_app
from eos_core.db import SessionLocal, get_db
from eos_core.events import OutboxEvent, current_impersonator, publish
from eos_core.tenant import organisation_scope, platform_scope
from eos_event_bus.application.consumers import discover as discover_consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

SA = {"email": "root@platform.example.com", "password": "RootPassw0rd!"}


def _drain() -> None:
    relay = Relay(InProcessTransport(discover_consumers()), EventBusConfig())
    for _ in range(30):
        if relay.run_once().claimed == 0:
            return
    raise AssertionError("the outbox did not drain")


def _impersonate(client, org_id: str, admin_token: str) -> tuple[dict, str, str]:
    """(impersonation headers, super admin id, impersonated user id)"""
    login = client.post("/api/v1/identity/auth/login", json=SA).json()
    user_id = client.get("/api/v1/identity/users", headers=auth(admin_token)).json()[0]["id"]
    r = client.post(
        f"/api/v1/tenancy/admin/organisations/{org_id}/impersonate",
        json={"user_id": user_id, "reason": "support ticket N3"},
        headers=auth(login["token"]),
    )
    assert r.status_code == 201, r.text
    return auth(r.json()["token"]), login["user"]["id"], user_id


def _created_event(email_user_id: str) -> OutboxEvent:
    with SessionLocal() as db, platform_scope():
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == "identity.user.created")).all()
        return next(r for r in rows if r.payload.get("user_id") == email_user_id)


def test_an_action_under_impersonation_is_audited_with_the_super_admin(client):
    a = register_and_login(client, slug=f"n3-{uuid.uuid4().hex[:6]}", academy_type="law-college")
    org_id = a["org"]["id"]
    imp, super_admin_id, admin_id = _impersonate(client, org_id, a["token"])

    # the impersonated admin's permissions apply, unchanged: the super admin creates a user as the admin
    me = client.get("/api/v1/identity/auth/me", headers=imp).json()
    assert me["id"] == admin_id and me["impersonated_by"] == super_admin_id
    body = {"email": f"s-{uuid.uuid4().hex[:6]}@n3.example.com", "name": "S", "password": "Passw0rd!x"}
    made = client.post("/api/v1/identity/users", json={**body, "roles": ["student"]}, headers=imp)
    assert made.status_code == 201, made.text
    # the same action by the admin's own token names nobody else
    body["email"] = f"t-{uuid.uuid4().hex[:6]}@n3.example.com"
    own = client.post("/api/v1/identity/users", json={**body, "roles": ["student"]}, headers=auth(a["token"]))
    assert own.status_code == 201, own.text

    assert _created_event(made.json()["id"]).impersonated_by == super_admin_id
    assert _created_event(own.json()["id"]).impersonated_by is None

    _drain()
    trail = client.get("/api/v1/audit/records?limit=200&action=user.created", headers=auth(a["token"])).json()
    records = {r["entity_id"]: r for r in trail["items"]}
    assert records[made.json()["id"]]["context"]["impersonated_by"] == super_admin_id
    assert "impersonated_by" not in records[own.json()["id"]]["context"]
    # nothing leaks into the next request: the context is per request
    assert current_impersonator() is None


def test_a_feature_modules_events_carry_the_impersonator_too():
    """Feature modules build their principal from the token themselves (no identity current_principal): the
    host's middleware sets the context for them as well."""
    probe = APIRouter()

    @probe.post("/publish")
    def publish_one(request: Request, db: Session = Depends(get_db)):
        org = request.state.organisation_id  # as a feature module does: its writes run in the caller's organisation
        with organisation_scope(org):  # (on Postgres row-level security refuses the row otherwise)
            ev = publish(db, "lms.probe.published", org, {"probe": True}, actor="someone")
            db.commit()
            return {"id": ev.id}

    with TestClient(create_app(extra_routers={"lms": probe})) as c:
        a = register_and_login(c, slug=f"n3f-{uuid.uuid4().hex[:6]}", academy_type="dance-academy")
        imp, super_admin_id, _ = _impersonate(c, a["org"]["id"], a["token"])
        via_imp = c.post("/api/v1/lms/publish", headers=imp)
        own = c.post("/api/v1/lms/publish", headers=auth(a["token"]))
        assert via_imp.status_code == own.status_code == 200, (via_imp.text, own.text)
    with SessionLocal() as db, platform_scope():
        assert db.get(OutboxEvent, via_imp.json()["id"]).impersonated_by == super_admin_id
        assert db.get(OutboxEvent, own.json()["id"]).impersonated_by is None
