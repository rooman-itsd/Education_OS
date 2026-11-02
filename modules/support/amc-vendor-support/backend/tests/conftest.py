"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/amc_vendor_support_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/amc-vendor-support"
NOW = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
VENDOR = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(scope="session")
def client():
    from eos_amc_vendor_support.api.router import router
    from eos_core.db import init_db
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
    from eos_amc_vendor_support.application import service

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
    """(action, reason) of the audit entries for one entity, oldest first."""
    from eos_amc_vendor_support.infrastructure.models import AuditEntry
    from eos_core.db import SessionLocal
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(r.action, r.reason) for r in rows]


def contract_body(**over) -> dict:
    body = {
        "vendor_id": VENDOR,
        "title": "Lift maintenance, main block",
        "coverage_type": "comprehensive",
        "scope": "Quarterly service and breakdown calls",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
        "value": {"amount": "120000.00", "currency": "INR"},
        "response_hours": 4,
        "resolution_hours": 24,
        "preventive_visits_per_year": 4,
        "vendor_contacts": [{"name": "Service desk", "phone": "000", "email": "desk@vendor.example"}],
        "renewal_notice_days": 60,
    }
    body.update(over)
    return body


class Desk:
    """An organisation with a contract manager, a coordinator and a viewer. Requests go through the HTTP API."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.manager_id, self.manager = org.user("amc-vendor-support-contract-manager")
        self.coordinator_id, self.coordinator = org.user("amc-vendor-support-coordinator")
        self.viewer_id, self.viewer = org.user("amc-vendor-support-viewer")

    @staticmethod
    def ok(response):
        assert response.status_code in (200, 201, 204), response.text
        return response.json() if response.status_code != 204 else None

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(f"{BASE}{path}", headers=headers or self.manager)

    def post(self, path: str, body, headers: dict | None = None):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers or self.manager)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers or self.manager)

    def delete(self, path: str, headers: dict | None = None):
        return self.client.delete(f"{BASE}{path}", headers=headers or self.manager)

    def draft(self, **over) -> dict:
        return self.ok(self.post("/contracts", contract_body(**over)))

    def active(self, **over) -> dict:
        contract = self.draft(**over)
        return self.ok(self.post(f"/contracts/{contract['id']}/activate", {}))

    def item(self, contract_id: str, description: str = "Lift 2", reference: dict | None = None) -> dict:
        body = {"description": description}
        if reference is not None:
            body["reference"] = reference
        return self.ok(self.post(f"/contracts/{contract_id}/covered-items", body))

    def engagement(self, contract_id: str, **over) -> dict:
        body = {"contract_id": contract_id, "kind": "breakdown_call", "description": "Lift stuck on floor 3"}
        body.update(over)
        return self.ok(self.post("/engagements", body, self.coordinator))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)


def days(n: int) -> str:
    """TODAY plus n days, as the contract's date string."""
    return (TODAY + timedelta(days=n)).isoformat()
