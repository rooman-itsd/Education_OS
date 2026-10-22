"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/hostel_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_hostel.api.router import router
from eos_hostel.application import service
from eos_hostel.infrastructure.models import new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# A Monday morning; every test works relative to it.
NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
BASE = "/api/v1/hostel"
YEAR = "2026-27"


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
    """One organisation with helpers to mint users holding hostel roles."""

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


def at(hour: int, minute: int = 0, day: int = 12) -> str:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC).isoformat()


class Campus:
    """An organisation with one hostel, one double room and staff of every role."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        _, self.admin = org.user("hostel-admin")
        self.warden_id, self.warden = org.user("hostel-warden")
        _, self.security = org.user("hostel-security")
        _, self.viewer = org.user("hostel-viewer")
        self.hostel = self.post("/hostels", {"name": "North Block", "occupancy_type": "women"}, self.admin).json()
        self.room = self.post(
            f"/hostels/{self.hostel['id']}/rooms", {"number": "101", "room_type": "double", "capacity": 2}, self.admin
        ).json()

    def post(self, path: str, body: dict | list | None, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)

    def resident(
        self, bed: str = "1", room_id: str | None = None, role: str = "hostel-resident"
    ) -> tuple[str, dict, dict]:
        """A checked-in resident holding `role`: (person_id, headers, allocation)."""
        person_id, headers = self.org.user(role)
        alloc = self.post(
            "/allocations",
            {
                "person_id": person_id,
                "room_id": room_id or self.room["id"],
                "bed": bed,
                "academic_year": YEAR,
                "from": "2026-10-01",
                "to": "2027-05-31",
            },
            self.warden,
        )
        assert alloc.status_code == 201, alloc.text
        r = self.post(f"/allocations/{alloc.json()['id']}/check-in", None, self.warden)
        assert r.status_code == 200, r.text
        return person_id, headers, r.json()


@pytest.fixture
def campus(client, org) -> Campus:
    return Campus(client, org)


def events(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(OutboxEvent.occurred_at)
        )
        return [r.payload for r in rows]
