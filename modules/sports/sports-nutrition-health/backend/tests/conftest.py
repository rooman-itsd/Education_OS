"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/sports_nutrition_health_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_sports_nutrition_health.api.router import router
from eos_sports_nutrition_health.application import consumers, service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
BASE = "/api/v1/sports-nutrition-health"
ADMIN = "sports-nutrition-health-admin"
MEDICAL = "sports-nutrition-health-medical"
NUTRITIONIST = "sports-nutrition-health-nutritionist"
COACH = "sports-nutrition-health-coach"
ATHLETE = "sports-nutrition-health-athlete"


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


@dataclass(frozen=True)
class Event:
    """The shape the event bus hands a consumer (eos_event_bus.domain.models.Event)."""

    organisation_id: str | None
    payload: dict
    name: str = consumers.ATHLETE_REGISTERED
    id: str = field(default_factory=new_id)


def deliver(event: Event) -> None:
    """What the event bus does: the handler in its own session, then commit."""
    with SessionLocal() as db:
        consumers.CONSUMERS[event.name](db, event)
        db.commit()


class Org:
    """One organisation with helpers to mint users and create rows through the API."""

    def __init__(self, client) -> None:
        self.id = new_id()
        self.client = client
        _, self.admin = self.user(ADMIN, MEDICAL)

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def link(self, athlete_id: str, user_id: str) -> None:
        """athlete-performance registered this athlete with this user."""
        deliver(Event(self.id, {"organisation_id": self.id, "athlete_id": athlete_id, "user_id": user_id}))

    def post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def plan(self, athlete_id: str, **kw) -> dict:
        body = {
            "athlete_id": athlete_id,
            "title": "Competition phase",
            "goal": "performance",
            "start_date": "2026-10-01",
            "review_due_on": "2026-11-01",
            "status": "active",
        }
        return self.post("/nutrition-plans", {**body, **kw})

    def injury(self, athlete_id: str, headers: dict | None = None, **kw) -> dict:
        body = {
            "athlete_id": athlete_id,
            "body_part": "Left hamstring",
            "severity": "moderate",
            "occurred_on": "2026-10-20",
            "status": "active",
        }
        return self.post("/injuries", {**body, **kw}, headers)

    def appointment(self, athlete_id: str, practitioner_id: str, headers: dict | None = None, **kw) -> dict:
        body = {
            "athlete_id": athlete_id,
            "practitioner_id": practitioner_id,
            "appointment_type": "physiotherapy",
            "scheduled_at": "2026-10-30T10:00:00+00:00",
            "status": "scheduled",
        }
        return self.post("/appointments", {**body, **kw}, headers)


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
