"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/sports_facilities_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))
os.environ["SPORTS_FACILITIES_TIMEZONE"] = "Asia/Kolkata"  # UTC+05:30: local dates differ from UTC ones

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_sports_facilities.api.router import router
from eos_sports_facilities.application import service
from eos_sports_facilities.infrastructure.models import AuditEntry
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# Thursday 29 October 2026, 14:30 in Kolkata.
NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
BASE = "/api/v1/sports-facilities"
ADMIN = "sports-facilities-admin"
STAFF = "sports-facilities-staff"
COACH = "sports-facilities-coach"
VIEWER = "sports-facilities-viewer"


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(service, "clock", lambda: NOW)
    return NOW


class Org:
    """One organisation with helpers to mint users and seed facilities through the API."""

    def __init__(self, client) -> None:
        self.id = new_id()
        self.client = client
        _, self.admin = self.user(ADMIN)

    def user(self, *roles: str) -> tuple[str, dict]:
        user_id = new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def facility(self, name: str = "Synthetic athletics track", **kw) -> dict:
        body = {"name": name, "facility_type": "track", "sports": ["Athletics"], "indoor": False, **kw}
        return self.post("/facilities", body)

    def space(self, facility_id: str, name: str = "Lanes 1-4", **kw) -> dict:
        return self.post(f"/facilities/{facility_id}/spaces", {"name": name, **kw})

    def usage(self, facility_id: str, used_from: str, used_to: str, purpose: str = "training", **kw) -> dict:
        body = {"facility_id": facility_id, "used_from": used_from, "used_to": used_to, "purpose": purpose, **kw}
        return self.post("/usage", body)


@pytest.fixture
def org(client) -> Org:
    return Org(client)


@pytest.fixture
def other_org(client) -> Org:
    return Org(client)


def outbox(organisation_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        if name:
            q = q.where(OutboxEvent.name == name)
        return list(db.scalars(q.order_by(OutboxEvent.occurred_at)))


def audit(organisation_id: str) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        return list(db.scalars(q.order_by(AuditEntry.occurred_at)))
