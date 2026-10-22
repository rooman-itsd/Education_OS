"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain and application tests run without it."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/helpdesk_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/helpdesk"
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_helpdesk.api.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clock(monkeypatch):
    """The service's clock, frozen at NOW; tests move it with clock.set()."""
    from eos_helpdesk.application import service

    class Clock:
        now = NOW

        def set(self, value: datetime) -> None:
            self.now = value

    frozen = Clock()
    monkeypatch.setattr(service, "clock", lambda: frozen.now)
    return frozen


class Org:
    """One organisation with helpers to mint users holding helpdesk roles."""

    def __init__(self) -> None:
        from eos_core.db import new_id

        self.id = new_id()

    def user(self, *roles: str) -> tuple[str, dict]:
        from eos_core.db import new_id
        from eos_core.security import create_token

        user_id = new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org() -> Org:
    return Org()


@pytest.fixture
def other_org() -> Org:
    return Org()


def outbox(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, oldest first."""
    from eos_core.db import SessionLocal
    from eos_core.events import OutboxEvent
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
        )
        return [r.payload for r in rows]


def audit(organisation_id: str, entity_id: str) -> list[tuple[str, str | None]]:
    """(action, reason) of the audit entries for one entity, oldest first."""
    from eos_core.db import SessionLocal
    from eos_helpdesk.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(r.action, r.reason) for r in rows]


class Desk:
    """An organisation with an admin, a lead, two agents in the IT queue, a viewer, a requester, two queues and an
    IT category. Requests go through the HTTP API."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.admin_id, self.admin = org.user("helpdesk-admin")
        self.lead_id, self.lead = org.user("helpdesk-lead")
        self.agent_id, self.agent = org.user("helpdesk-agent")
        self.agent2_id, self.agent2 = org.user("helpdesk-agent")
        self.outsider_id, self.outsider = org.user("helpdesk-agent")  # an agent in no queue
        self.viewer_id, self.viewer = org.user("helpdesk-viewer")
        self.requester_id, self.requester = org.user("helpdesk-requester")
        self.it = self.ok(
            self.post(
                "/queues", {"name": "IT", "member_ids": [self.agent_id, self.agent2_id, self.lead_id]}, self.admin
            )
        )
        self.office = self.ok(self.post("/queues", {"name": "Academic office", "member_ids": []}, self.admin))
        self.category = self.ok(
            self.post(
                "/categories",
                {"name": "Account access", "default_queue_id": self.it["id"], "default_priority": "high"},
                self.admin,
            )
        )

    @staticmethod
    def ok(response):
        assert response.status_code in (200, 201), response.text
        return response.json()

    def post(self, path: str, body, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def patch(self, path: str, body, headers: dict):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)

    def raise_ticket(self, title: str = "Cannot sign in", headers: dict | None = None) -> dict:
        body = {"category_id": self.category["id"], "title": title, "description": "Password reset loops"}
        return self.ok(self.post("/me/tickets", body, headers or self.requester))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)
