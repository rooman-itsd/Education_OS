"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/training_video_analysis_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_training_video_analysis.api.router import router
from eos_training_video_analysis.application import consumers, service
from eos_training_video_analysis.infrastructure.models import AuditEntry
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import literal_column, select

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
BASE = "/api/v1/training-video-analysis"
ADMIN = "training-video-analysis-admin"
COACH = "training-video-analysis-coach"
ATHLETE = "training-video-analysis-athlete"


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
        self.admin_id, self.admin = self.user(ADMIN)

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def link(self, athlete_id: str, user_id: str) -> None:
        """athlete-performance registered this athlete with this user."""
        deliver(Event(self.id, {"organisation_id": self.id, "athlete_id": athlete_id, "user_id": user_id}))

    def athlete_user(self, athlete_id: str | None = None) -> tuple[str, dict]:
        """A signed-in athlete linked to an athlete id; returns (athlete_id, headers)."""
        athlete_id = athlete_id or new_id()
        user_id, headers = self.user(ATHLETE)
        self.link(athlete_id, user_id)
        return athlete_id, headers

    def post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def patch(self, path: str, body: dict, headers: dict | None = None):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers or self.admin)

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(f"{BASE}{path}", headers=headers or self.admin)

    def plan(self, **kw) -> dict:
        body = {
            "title": "Pre-season block",
            "coach_id": self.admin_id,
            "start_date": "2026-10-01",
            "end_date": "2026-12-31",
        }
        return self.post("/plans", {**body, **kw})

    def drill(self, code: str = "DRILL-AGI-01", **kw) -> dict:
        body = {"code": code, "title": "Ladder agility shuffle", "category": "Agility", "intensity": "high"}
        return self.post("/drills", {**body, **kw})

    def session(self, **kw) -> dict:
        body = {
            "coach_id": self.admin_id,
            "title": "Morning speed work",
            "scheduled_start": "2026-10-29T01:00:00+00:00",
            "scheduled_end": "2026-10-29T02:30:00+00:00",
        }
        return self.post("/sessions", {**body, **kw})

    def video(self, **kw) -> dict:
        body = {
            "uploader_id": self.admin_id,
            "title": "Sprint mechanics cam A",
            "video_url": "https://files.example.com/videos/abc.mp4",
            "duration_seconds": 245.5,
            "recorded_at": "2026-10-29T02:00:00+00:00",
        }
        return self.post("/videos", {**body, **kw})

    def annotation(self, video_id: str, **kw) -> dict:
        body = {"author_id": self.admin_id, "start_timestamp": 42.5, "content": "Knee angle too low", **kw}
        return self.post(f"/videos/{video_id}/annotations", body)


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


def audit(organisation_id: str, entity_type: str | None = None) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        if entity_type:
            q = q.where(AuditEntry.entity_type == entity_type)
        # the clock is frozen, so entries of one test share occurred_at: SQLite rowid keeps the order written
        return list(db.scalars(q.order_by(AuditEntry.occurred_at, literal_column("rowid"))))
