"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/tournament_events_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))
os.environ["TOURNAMENT_EVENTS_TIMEZONE"] = "Asia/Kolkata"

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_tournament_events.api.router import router
from eos_tournament_events.application import consumers, service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# 30 October 2026, 09:00 UTC (14:30 in Kolkata)
NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
BASE = "/api/v1/tournament-events"
ADMIN = "tournament-events-admin"
COACH = "tournament-events-coach"
ATHLETE = "tournament-events-athlete"
VIEWER = "tournament-events-viewer"


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
    occurred_at: datetime = NOW


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
        _, self.admin = self.user(ADMIN)

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def link(self, athlete_id: str, user_id: str) -> None:
        """athlete-performance registered this athlete with this user."""
        deliver(Event(self.id, {"organisation_id": self.id, "athlete_id": athlete_id, "user_id": user_id}))

    def post(self, path: str, body: dict | None = None, headers: dict | None = None, status: int = 201) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == status, r.text
        return r.json()

    def tournament(self, publish: bool = True, **kw) -> dict:
        body = {
            "name": "Inter-University Athletics Meet 2026",
            "discipline": "Athletics",
            "level": "inter_university",
            "format": "heats_and_finals",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "venue": "University Stadium",
            "registration_closes_on": "2026-11-05",
        }
        t = self.post("/tournaments", {**body, **kw})
        if publish:
            t = self.post(f"/tournaments/{t['id']}/publish", status=200)
        return t

    def entry(self, tournament_id: str, athlete_ids: list[str], category: str = "Men's 100 m", **kw) -> dict:
        body = {"category": category, "athlete_ids": athlete_ids, "status": "confirmed"}
        return self.post(f"/tournaments/{tournament_id}/entries", {**body, **kw})

    def fixture(self, tournament_id: str, entry_ids: list[str], at: str = "2026-11-10T04:30:00Z", **kw) -> dict:
        body = {"round": "Heat 1", "entry_ids": entry_ids, "scheduled_at": at, "status": "scheduled"}
        return self.post(f"/tournaments/{tournament_id}/fixtures", {**body, **kw})


@pytest.fixture
def org(client) -> Org:
    return Org(client)


@pytest.fixture
def other_org(client) -> Org:
    return Org(client)


@pytest.fixture
def later(monkeypatch):
    """Move the clock: later(datetime) makes that the current time."""

    def move(at: datetime) -> None:
        monkeypatch.setattr(service, "clock", lambda: at)

    return move


def outbox(organisation_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        if name:
            q = q.where(OutboxEvent.name == name)
        return list(db.scalars(q.order_by(OutboxEvent.occurred_at)))
