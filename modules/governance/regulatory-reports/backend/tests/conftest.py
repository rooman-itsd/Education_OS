"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/regulatory_reports_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/regulatory-reports"
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
TODAY = NOW.date()


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_regulatory_reports.api.router import router
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
    from eos_regulatory_reports.application import service

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
    """(action, reason) of the audit entries for one entity."""
    from eos_core.db import SessionLocal
    from eos_regulatory_reports.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry).where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
        )
        return [(r.action, r.reason) for r in rows]


def days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


class Desk:
    """An organisation's compliance desk: a coordinator, two preparers and a viewer, with request helpers."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.coordinator_id, self.coordinator = org.user("regulatory-reports-coordinator")
        self.preparer_id, self.preparer = org.user("regulatory-reports-preparer")
        self.preparer2_id, self.preparer2 = org.user("regulatory-reports-preparer")
        self.viewer_id, self.viewer = org.user("regulatory-reports-viewer")
        self._n = 0

    @staticmethod
    def ok(response):
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json()

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(BASE + path, headers=headers or self.coordinator)

    def post(self, path: str, body=None, headers: dict | None = None):
        return self.client.post(BASE + path, json=body, headers=headers or self.coordinator)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(BASE + path, json=body, headers=headers or self.coordinator)

    def obligation(self, **over) -> dict:
        body = {
            "title": "Annual report to the regulator",
            "authority": "State Council",
            "recurrence": "annual",
            "default_owner_id": self.preparer_id,
        }
        body.update(over)
        return self.ok(self.post("/obligations", body))

    def filing(self, obligation_id: str | None = None, **over) -> dict:
        self._n += 1
        body = {
            "period_label": f"P{self._n}",
            "period_start": days(-120),
            "period_end": days(-30),
            "due_on": days(10),
        }
        body.update(over)
        oid = obligation_id or self.obligation()["id"]
        return self.ok(self.post(f"/obligations/{oid}/filings", body))

    def move(self, filing_id: str, status: str, headers: dict | None = None, **extra) -> dict:
        return self.ok(self.post(f"/filings/{filing_id}/status", {"status": status, **extra}, headers))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)
