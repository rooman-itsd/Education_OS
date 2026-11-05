"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/grievance_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/grievance"
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)  # a Thursday
DESCRIPTION = "The hostel warden refused to return my deposit after I vacated the room."

SETTINGS = [
    "GRIEVANCE_CASE_NUMBER_PREFIX",
    "GRIEVANCE_STUDENT_GRIEVANCE_ACKNOWLEDGE_DAYS",
    "GRIEVANCE_STUDENT_GRIEVANCE_DECIDE_DAYS",
    "GRIEVANCE_RAGGING_ACKNOWLEDGE_DAYS",
    "GRIEVANCE_RAGGING_DECIDE_DAYS",
    "GRIEVANCE_SEXUAL_HARASSMENT_ACKNOWLEDGE_DAYS",
    "GRIEVANCE_SEXUAL_HARASSMENT_DECIDE_DAYS",
    "GRIEVANCE_APPEAL_WINDOW_DAYS",
    "GRIEVANCE_DAY_COUNTING",
]


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_grievance.api.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    """No GRIEVANCE_* setting leaks in from the shell; tests that need one set it."""
    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def clock(monkeypatch):
    """The service's clock, frozen at NOW; tests move it with clock.set() or clock.advance()."""
    from eos_grievance.application import service

    class Clock:
        """Time stands still between calls to move it, except for one microsecond after each reading, so rows written in the
        same test keep their order."""

        now = NOW

        def set(self, value: datetime) -> None:
            self.now = value

        def advance(self, **kwargs) -> None:
            self.now = self.now + timedelta(**kwargs)

        def read(self) -> datetime:
            value = self.now
            self.now = value + timedelta(microseconds=1)
            return value

    frozen = Clock()
    monkeypatch.setattr(service, "clock", frozen.read)
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
    from eos_core.db import SessionLocal
    from eos_grievance.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(r.action, r.reason) for r in rows]


class Campus:
    """An organisation with a coordinator, an SGRC, an anti-ragging committee, an ICC and an ombudsperson committee,
    each with one member who holds the committee-member role, and a complainant, with request helpers."""

    def __init__(self, client, org: Org) -> None:
        from eos_grievance.infrastructure import notifier

        self.client, self.org = client, org
        notifier.sent.clear()
        self.coordinator_id, self.coordinator = org.user("grievance-coordinator")
        self.viewer_id, self.viewer = org.user("grievance-viewer")
        self.complainant_id, self.complainant = org.user("grievance-complainant")
        self.other_id, self.other = org.user("grievance-complainant")
        self.members: dict[str, tuple[str, dict]] = {}
        self.committees: dict[str, dict] = {}
        for kind in ("sgrc", "anti_ragging", "icc", "ombudsperson"):
            self.members[kind] = org.user("grievance-committee-member")
            self.committees[kind] = self.ok(
                self.post(
                    "/committees",
                    {
                        "name": f"{kind} committee",
                        "kind": kind,
                        "members": [{"person_id": self.members[kind][0], "role": "chair"}],
                    },
                    self.coordinator,
                )
            )

    @staticmethod
    def ok(response):
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json()

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(BASE + path, headers=headers or self.coordinator)

    def post(self, path: str, body=None, headers: dict | None = None):
        return self.client.post(BASE + path, json=body, headers=headers or self.coordinator)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(BASE + path, json=body, headers=headers or self.coordinator)

    def member(self, kind: str = "sgrc") -> dict:
        return self.members[kind][1]

    def file(self, track: str = "student_grievance", headers: dict | None = None, **over) -> dict:
        body = {"track": track, "category": "Hostel", "description": DESCRIPTION}
        body.update(over)
        return self.ok(self.post("/me/grievances", body, headers or self.complainant))

    def move(self, case_id: str, status: str, kind: str = "sgrc", **extra) -> dict:
        return self.ok(self.post(f"/grievances/{case_id}/status", {"status": status, **extra}, self.member(kind)))

    def to_inquiry(self, case_id: str, kind: str = "sgrc") -> None:
        self.move(case_id, "acknowledged", kind)
        self.move(case_id, "under_inquiry", kind)

    def decide(self, case_id: str, kind: str = "sgrc") -> dict:
        self.to_inquiry(case_id, kind)
        body = {"outcome": "upheld", "findings": "The deposit was withheld without cause."}
        return self.ok(self.post(f"/grievances/{case_id}/decision", body, self.member(kind)))


@pytest.fixture
def campus(client, org, clock) -> Campus:
    return Campus(client, org)
