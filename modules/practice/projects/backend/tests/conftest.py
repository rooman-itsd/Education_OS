"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/projects_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_projects.api.router import router
from eos_projects.application import service
from eos_projects.infrastructure.models import AuditEntry, new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import literal_column, select

# 06:00 UTC on Wednesday 4 November 2026 is 11:30 in Asia/Kolkata; every test works relative to it.
NOW = datetime(2026, 11, 4, 6, 0, tzinfo=UTC)
BASE = "/api/v1/projects"
PERIOD = {"starts_on": "2026-08-01", "ends_on": "2027-04-30"}


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    """NOW, moving on a millisecond per reading so rows keep the order they were written in, as in real use."""
    ticks = count()
    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(milliseconds=next(ticks)))
    return NOW


class Org:
    """One organisation with helpers to mint users holding projects roles (or any profile role)."""

    def __init__(self) -> None:
        self.id = new_id()

    def user(self, *roles: str) -> tuple[str, dict]:
        user_id = new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org() -> Org:
    return Org()


@pytest.fixture
def other_org() -> Org:
    return Org()


class Studio:
    """An organisation with a coordinator, a viewer, two guides, three learners and one active project: learner 1
    leads it with learner 2 on the team, guide 1 guides it. Learner 3 and guide 2 are on no project."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.coordinator_id, self.coordinator = org.user("projects-coordinator")
        _, self.viewer = org.user("projects-viewer")
        self.guide_id, self.guide = org.user("projects-guide")
        self.guide2_id, self.guide2 = org.user("projects-guide")
        self.lead_id, self.lead = org.user("projects-member")
        self.member_id, self.member = org.user("projects-member")
        self.outsider_id, self.outsider = org.user("projects-member")
        self.project = self.new_project("Solar irrigation pump")

    def new_project(self, title: str, **over) -> dict:
        body = {
            "title": title,
            "summary": "A test project",
            "kind": "Capstone",
            "academic_year": "2026-27",
            **PERIOD,
            "member_ids": [self.lead_id, self.member_id],
            "lead_id": self.lead_id,
            "guide_ids": [self.guide_id],
            **over,
        }
        r = self.post("/projects", body, self.coordinator)
        assert r.status_code == 201, r.text
        return r.json()

    def milestone(self, title: str = "Design review", due_on: str = "2026-11-10", project_id: str | None = None):
        r = self.post(
            f"/projects/{project_id or self.project['id']}/milestones",
            {"title": title, "due_on": due_on, "weight": 20},
            self.guide,
        )
        assert r.status_code == 201, r.text
        return r.json()

    def submit(self, milestone_id: str, headers: dict | None = None, note: str = "Draft attached"):
        return self.post(f"/milestones/{milestone_id}/submissions", {"note": note}, headers or self.member)

    def propose(self, headers: dict, title: str = "Campus compost study") -> dict:
        r = self.post("/projects", {"title": title, "kind": "Research", **PERIOD}, headers)
        assert r.status_code == 201, r.text
        return r.json()

    def post(self, path: str, body: dict | list | None, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def put(self, path: str, body: dict, headers: dict):
        return self.client.put(f"{BASE}{path}", json=body, headers=headers)

    def patch(self, path: str, body: dict, headers: dict):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers)

    def delete(self, path: str, headers: dict):
        return self.client.delete(f"{BASE}{path}", headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)


@pytest.fixture
def studio(client, org) -> Studio:
    return Studio(client, org)


def events(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, in the order they were written."""
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(literal_column("rowid"))  # insertion order; the tests always run on SQLite
        )
        return [r.payload for r in rows]


def audit(entity_id: str) -> list[tuple[str | None, str]]:
    """(actor, action) of every audit entry for one record."""
    with SessionLocal() as db:
        rows = db.scalars(select(AuditEntry).where(AuditEntry.entity_id == entity_id))
        return [(r.actor, r.action) for r in rows]
