"""Helpers shared by the integration-hub tests (kept out of conftest.py so test files can import them by a unique
name)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import create_user
from sqlalchemy import select

BASE = "/api/v1/integration-hub"
NOW = datetime(2026, 11, 5, 6, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now = self.now + timedelta(**delta)


def _user(org_id: str | None, roles: list[str], label: str, super_admin: bool = False):
    with SessionLocal() as db, organisation_scope(org_id) if org_id else platform_scope():
        u = create_user(
            db,
            organisation_id=org_id,
            email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
            name=label,
            password="Secret123!",
            roles=roles,
            is_super_admin=super_admin,
        )
        db.commit()
        return u.id


class Org:
    """An organisation with an org admin, two members (the implicit `member` role) and a user who holds a role the
    hub's catalogue does not name."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.ids = {
            "admin": _user(self.id, ["org-admin"], "admin"),
            "member": _user(self.id, [], "member"),
            "member2": _user(self.id, [], "member2"),
            "faculty": _user(self.id, ["faculty"], "faculty"),
        }
        roles = {"admin": ["org-admin"], "member": [], "member2": [], "faculty": ["faculty"]}
        self.headers = {
            k: auth(create_token(user_id=uid, organisation_id=self.id, roles=roles[k])) for k, uid in self.ids.items()
        }

    @property
    def admin(self) -> dict:
        return self.headers["admin"]

    @property
    def member(self) -> dict:
        return self.headers["member"]

    def token(self, who: str) -> str:
        return self.headers[who]["Authorization"].split(" ", 1)[1]


class SuperAdmin:
    def __init__(self):
        self.id = _user(None, ["super-admin"], "root", super_admin=True)
        self.headers = auth(
            create_token(user_id=self.id, organisation_id=None, roles=["super-admin"], super_admin=True)
        )


def connection_body(**fields) -> dict:
    body = {"adapter": "fake-adapter", "provider": "fakecert", "port": "certificate-issuance", "mode": "sandbox"}
    body.update(fields)
    return body


def create(client, org: Org, **fields) -> dict:
    r = client.post(f"{BASE}/connections", json=connection_body(**fields), headers=org.admin)
    assert r.status_code == 201, r.text
    return r.json()


def put_credential(client, org: Org, cid: str, name: str, value: str):
    r = client.put(f"{BASE}/connections/{cid}/credentials/{name}", json={"value": value}, headers=org.admin)
    assert r.status_code == 200, r.text
    return r.json()


def enabled_cert(client, org: Org, **fields) -> dict:
    """A fakecert connection in sandbox with both credentials, enabled."""
    c = create(client, org, **fields)
    put_credential(client, org, c["id"], "api_key", "cert-api-key-value")
    put_credential(client, org, c["id"], "webhook_secret", "cert-webhook-secret")
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 200, r.text
    return r.json()


def authorised_meet(client, org: Org, adapter) -> dict:
    """A fakemeet connection authorised through the OAuth callback and enabled."""
    c = create(client, org, provider="fakemeet", port="meetings", settings={"account_id": "acc-1"})
    put_credential(client, org, c["id"], "client_id", "meet-client-id")
    put_credential(client, org, c["id"], "client_secret", "meet-client-secret")
    r = client.post(
        f"{BASE}/connections/{c['id']}/authorise", json={"return_url": "https://app.example.test/x"}, headers=org.admin
    )
    assert r.status_code == 200, r.text
    state = parse_qs(urlsplit(r.json()["authorize_url"]).query)["state"][0]
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter", params={"state": state, "code": "good-code"}, follow_redirects=False
    )
    assert r.status_code == 302 and "status=connected" in r.headers["location"], r.headers
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 200, r.text
    return r.json()


def state_of(authorize_url: str) -> str:
    return parse_qs(urlsplit(authorize_url).query)["state"][0]


def wear_connection(client, org):
    c = create(client, org, provider="fakewear", port="wearable-data")
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 200, r.text
    return c


def link_account(client, org, who="member", subject=None, adapter=None):
    if subject and adapter:
        adapter.STATE["subject"] = subject
    r = client.post(
        f"{BASE}/me/account-links",
        json={
            "port": "wearable-data",
            "provider": "fakewear",
            "purpose": "Share daily training data with your coaches",
            "return_url": "https://app.example.test/me",
        },
        headers=org.headers[who],
    )
    assert r.status_code == 201, r.text
    start = r.json()
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start["authorize_url"]), "code": "good-code"},
        follow_redirects=False,
    )
    assert r.headers["location"].endswith("status=connected"), r.headers
    return start["account_link"]


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]


def all_outbox(organisation_id: str) -> list[OutboxEvent]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        return list(db.scalars(q.order_by(OutboxEvent.occurred_at)))


def audit_actions(organisation_id: str | None) -> list[str]:
    from eos_audit.domain.models import AuditRecord

    with SessionLocal() as db, platform_scope():
        q = select(AuditRecord.action).where(AuditRecord.module == "integration-hub")
        q = q.where(AuditRecord.organisation_id == organisation_id) if organisation_id else q
        return list(db.scalars(q))


def code(r) -> str:
    return r.json()["code"]


def key_of(connection: dict) -> str:
    """The connection key from its inbound URL."""
    url = connection["inbound_urls"][0]
    return url.split("/inbound/fake-adapter/", 1)[1].split("/", 1)[0]


def body(data: dict) -> bytes:
    return json.dumps(data).encode()
