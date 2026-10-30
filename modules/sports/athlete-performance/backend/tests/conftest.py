"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/athlete_performance_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_athlete_performance.api.router import router
from eos_athlete_performance.application import service
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
BASE = "/api/v1/athlete-performance"
ADMIN = "athlete-performance-admin"
COACH = "athlete-performance-coach"
MEDICAL = "athlete-performance-medical"
ATHLETE = "athlete-performance-athlete"
VIEWER = "athlete-performance-viewer"


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
    """One organisation with helpers to mint users and seed a small catalogue through the API."""

    def __init__(self, client) -> None:
        self.id = new_id()
        self.client = client
        _, self.admin = self.user(ADMIN)

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def discipline(self, name: str = "Athletics (sprints)", category: str = "individual") -> dict:
        return self.post("/disciplines", {"name": name, "category": category, "active": True})

    def metric(self, name: str = "100 m sprint", unit: str = "s", direction: str = "lower_is_better", **kw) -> dict:
        return self.post("/metrics", {"name": name, "unit": unit, "direction": direction, **kw})

    def athlete(self, discipline_id: str, name: str = "Asha Rao", **kw) -> dict:
        body = {"full_name": name, "primary_discipline_id": discipline_id, "status": "active", **kw}
        return self.post("/athletes", body)

    def result(self, athlete_id: str, metric_id: str, value: float, at: str = "2026-10-20T08:00:00+00:00", **kw):
        body = {
            "athlete_id": athlete_id,
            "metric_id": metric_id,
            "value": value,
            "recorded_at": at,
            "context": "training",
        }
        return self.post("/results", {**body, **kw})


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
