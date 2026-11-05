"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/transport_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_transport.api.router import router
from eos_transport.application import service
from eos_transport.infrastructure.models import new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# A Tuesday morning; every test works relative to it.
NOW = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
BASE = "/api/v1/transport"
TERM = {"valid_from": "2026-10-27", "valid_to": "2027-03-31"}


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
    """One organisation with helpers to mint users holding transport roles."""

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


def at(hour: int, minute: int = 0, day: int = 27) -> str:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC).isoformat()


class Campus:
    """An organisation with three stops, a 2-seat van, a signed-in driver, one assigned route and staff of every role."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        _, self.admin = org.user("transport-admin")
        _, self.viewer = org.user("transport-viewer")
        self.driver_person, self.driver = org.user("transport-driver")
        self.stops = [
            self.post("/stops", {"name": name, "latitude": lat, "longitude": 77.6}, self.admin).json()
            for name, lat in (("Main Gate", 12.90), ("Market", 12.95), ("Station", 13.00))
        ]
        self.vehicle = self.post(
            "/vehicles",
            {
                "registration_no": "KA01AB1234",
                "type": "van",
                "capacity": 2,
                "insurance_expires_on": "2027-06-30",
                "fitness_expires_on": "2027-06-30",
                "permit_expires_on": "2027-06-30",
            },
            self.admin,
        ).json()
        self.driver_row = self.post(
            "/drivers",
            {
                "person_id": self.driver_person,
                "name": "Test Driver",
                "licence_no": "DL-TEST-1",
                "licence_expires_on": "2028-01-31",
            },
            self.admin,
        ).json()
        self.route = self.new_route("R1")
        r = self.put(
            f"/routes/{self.route['id']}/assignment",
            {"vehicle_id": self.vehicle["id"], "driver_id": self.driver_row["id"]},
            self.admin,
        )
        assert r.status_code == 200, r.text
        self.route = r.json()

    def new_route(self, code: str, stops: list[dict] | None = None) -> dict:
        body = {
            "code": code,
            "name": f"Route {code}",
            "direction": "morning pick-up",
            "stops": [
                {"stop_id": s["id"], "sequence": i + 1, "scheduled_time": f"07:{i * 10:02d}"}
                for i, s in enumerate(stops or self.stops)
            ],
        }
        r = self.post("/routes", body, self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def post(self, path: str, body: dict | list | None, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def put(self, path: str, body: dict, headers: dict):
        return self.client.put(f"{BASE}{path}", json=body, headers=headers)

    def patch(self, path: str, body: dict, headers: dict):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)

    def rider(
        self, role: str = "transport-rider", stop: int = 0, route_id: str | None = None
    ) -> tuple[str, dict, dict]:
        """A rider holding `role` with an issued pass on the route: (person_id, headers, pass)."""
        person_id, headers = self.org.user(role)
        req = self.post(
            "/me/passes", {"route_id": route_id or self.route["id"], "stop_id": self.stops[stop]["id"], **TERM}, headers
        )
        assert req.status_code == 201, req.text
        r = self.post(f"/passes/{req.json()['id']}/decision", {"decision": "issued"}, self.admin)
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
