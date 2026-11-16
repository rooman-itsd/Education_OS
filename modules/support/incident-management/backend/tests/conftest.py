"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/incident_management_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/incident-management"
NOW = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
TICKET = {"module": "helpdesk", "entity": "ticket", "id": "hd-101", "relation": "related_ticket"}


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_incident_management.api.router import router
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
    from eos_incident_management.application import service

    class Clock:
        now = NOW

        def set(self, value: datetime) -> None:
            self.now = value

    frozen = Clock()
    monkeypatch.setattr(service, "clock", lambda: frozen.now)
    return frozen


class Org:
    """One organisation with helpers to mint users holding module roles."""

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
    """(action, reason) of the audit entries for one entity, in the order they were written."""
    from eos_core.db import SessionLocal
    from eos_incident_management.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.execute(
            select(AuditEntry.action, AuditEntry.reason)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, text_rowid())
        )
        return [(action, reason) for action, reason in rows]


def text_rowid():
    """SQLite's rowid: the insertion order, since the frozen clock gives every entry the same occurred_at."""
    from sqlalchemy import literal_column

    return literal_column("rowid")


def incident_body(**over) -> dict:
    body = {
        "title": "Campus Wi-Fi down in block A",
        "description": "Access points in block A drop every client",
        "affected_services": ["Wi-Fi"],
        "severity": "high",
    }
    body.update(over)
    return body


def problem_body(**over) -> dict:
    body = {"title": "Access point firmware crash", "description": "Firmware 4.2 crashes under load"}
    body.update(over)
    return body


def rca_body(**over) -> dict:
    body = {"summary": "Firmware bug", "root_cause": "Memory leak in firmware 4.2"}
    body.update(over)
    return body


class Desk:
    """An organisation with a responder, a problem manager and a viewer. Requests go through the HTTP API."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.responder_id, self.responder = org.user("incident-management-responder")
        self.manager_id, self.manager = org.user("incident-management-problem-manager")
        self.viewer_id, self.viewer = org.user("incident-management-viewer")

    @staticmethod
    def ok(response):
        assert response.status_code in (200, 201, 204), response.text
        return response.json() if response.status_code != 204 else None

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(f"{BASE}{path}", headers=headers or self.manager)

    def post(self, path: str, body, headers: dict | None = None):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers or self.manager)

    def put(self, path: str, body, headers: dict | None = None):
        return self.client.put(f"{BASE}{path}", json=body, headers=headers or self.manager)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers or self.manager)

    def delete(self, path: str, headers: dict | None = None):
        return self.client.delete(f"{BASE}{path}", headers=headers or self.manager)

    def incident(self, **over) -> dict:
        return self.ok(self.post("/incidents", incident_body(**over), self.responder))

    def move(self, incident_id: str, status: str, **extra) -> dict:
        return self.ok(self.post(f"/incidents/{incident_id}/status", {"status": status, **extra}, self.responder))

    def problem(self, **over) -> dict:
        return self.ok(self.post("/problems", problem_body(**over)))

    def published(self, problem_id: str) -> dict:
        self.ok(self.put(f"/problems/{problem_id}/rca", rca_body()))
        return self.ok(self.post(f"/problems/{problem_id}/rca/publish", {}))

    def action(self, problem_id: str, **over) -> dict:
        body = {"description": "Upgrade firmware to 4.3", "owner_id": self.responder_id, "due_date": days(7)}
        body.update(over)
        return self.ok(self.post(f"/problems/{problem_id}/actions", body))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)


def days(n: int) -> str:
    """TODAY plus n days, as the contract's date string."""
    return (TODAY + timedelta(days=n)).isoformat()
