"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/field_training_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_field_training.api.router import router
from eos_field_training.application import service
from eos_field_training.infrastructure.models import AuditEntry, new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# Tuesday 3 November 2026, 13:30 in Asia/Kolkata; every test works relative to it.
NOW = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
TODAY = "2026-11-03"
BASE = "/api/v1/field-training"
PERIOD = {"starts_on": "2026-11-02", "ends_on": "2026-12-31"}


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
    """One organisation with helpers to mint users holding roles."""

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


class Programme:
    """An organisation with a coordinator, a viewer, a supervisor attached to one site, and an open opening there
    with two seats, 40 required hours and applications allowed. Mints trainees on demand."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        _, self.coordinator = org.user("field-training-coordinator")
        _, self.viewer = org.user("field-training-viewer")
        self.supervisor_id, self.supervisor = org.user("field-training-supervisor")
        self.site = self.ok(
            self.post(
                "/sites",
                {
                    "name": "North Ward",
                    "kind": "Ward",
                    "address": "1 Test Road",
                    "contact_name": "Site Contact",
                    "contact_email": "contact@example.test",
                    "supervisor_ids": [self.supervisor_id],
                },
                self.coordinator,
            ),
            201,
        )
        self.opening = self.new_opening()

    def new_opening(self, publish: bool = True, **over) -> dict:
        body = {
            "site_id": self.site["id"],
            "title": "General rotation",
            "discipline": "General",
            **PERIOD,
            "seats": 2,
            "required_hours": 40,
            "allow_applications": True,
            "eligibility": "Second year onwards",
            "supervisor_ids": [self.supervisor_id],
            **over,
        }
        o = self.ok(self.post("/openings", body, self.coordinator), 201)
        if publish:
            o = self.ok(self.post(f"/openings/{o['id']}/publish", None, self.coordinator))
        return o

    def ok(self, response, status: int = 200) -> dict:
        assert response.status_code == status, response.text
        return response.json()

    def post(self, path: str, body, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def patch(self, path: str, body: dict, headers: dict):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)

    def trainee(self, role: str = "field-training-trainee") -> tuple[str, dict]:
        return self.org.user(role)

    def assigned(self, opening: dict | None = None, role: str = "field-training-trainee") -> tuple[str, dict, dict]:
        """A trainee assigned to the opening: (trainee_id, headers, placement)."""
        trainee_id, headers = self.trainee(role)
        body = {"opening_id": (opening or self.opening)["id"], "trainee_id": trainee_id}
        return trainee_id, headers, self.ok(self.post("/placements", body, self.coordinator), 201)

    def active(self, opening: dict | None = None, role: str = "field-training-trainee") -> tuple[str, dict, dict]:
        """A trainee with an active placement supervised by self.supervisor."""
        trainee_id, headers, p = self.assigned(opening, role)
        return trainee_id, headers, self.ok(self.post(f"/placements/{p['id']}/start", None, self.coordinator))

    def log(self, placement: dict, headers: dict, hours: float = 4, date: str = TODAY, **over):
        body = {"date": date, "hours": hours, "activities": "Observed and assisted with routine work", **over}
        return self.post(f"/placements/{placement['id']}/logs", body, headers)


@pytest.fixture
def prog(client, org) -> Programme:
    return Programme(client, org)


def events(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(OutboxEvent.occurred_at)
        )
        return [r.payload for r in rows]


def audit(entity_id: str) -> list[str]:
    """Audit actions recorded for one entity, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(AuditEntry).where(AuditEntry.entity_id == entity_id).order_by(AuditEntry.occurred_at))
        return [r.action for r in rows]
