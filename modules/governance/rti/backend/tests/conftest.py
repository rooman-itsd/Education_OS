"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/rti_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/rti"
# 14:30 in India on Thursday 5 November 2026 (the 6th has not begun there; UTC is still the 5th).
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
RTI_KEYS = (
    "RTI_REQUEST_NUMBER_PREFIX",
    "RTI_DEFAULT_CURRENCY",
    "RTI_NEARING_DEADLINE_DAYS",
    "RTI_RESPONSE_DAYS",
    "RTI_APPEAL_WINDOW_DAYS",
    "RTI_APPEAL_DECIDE_DAYS",
    "RTI_DAY_COUNTING",
)


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_rti.api.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clock(monkeypatch):
    """The service's clock, frozen at NOW; tests move it with clock.set()."""
    from eos_rti.application import service

    class Clock:
        now = NOW

        def set(self, value: datetime) -> None:
            self.now = value

    frozen = Clock()
    monkeypatch.setattr(service, "clock", lambda: frozen.now)
    return frozen


@pytest.fixture
def settings(monkeypatch):
    """Every RTI_* key unset, then the timeline values a test names. `settings(response_days=30)`."""
    for key in RTI_KEYS:
        monkeypatch.delenv(key, raising=False)

    def configure(**values) -> None:
        for name, value in values.items():
            monkeypatch.setenv(f"RTI_{name.upper()}", str(value))

    def unset(*names: str) -> None:
        for name in names:
            monkeypatch.delenv(f"RTI_{name.upper()}", raising=False)

    configure.unset = unset
    return configure


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


def audit(organisation_id: str, entity_id: str) -> list[str]:
    """The actions of the audit entries for one entity, sorted: the clock is frozen in tests, so every entry has the
    same time and the order they were written in is not recorded."""
    from eos_core.db import SessionLocal
    from eos_rti.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry).where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
        )
        return sorted(r.action for r in rows)


def days(n: int) -> str:
    """The date n days from today in India, as an ISO string."""
    return (TODAY + timedelta(days=n)).isoformat()


APPLICANT = {
    "name": "Asha Verma",
    "address": "12 Park Road, Mysuru",
    "email": "asha.verma@example.org",
    "phone": "+91 98450 00000",
}


class Desk:
    """An organisation's RTI cell: an officer, a custodian, the appellate authority and a viewer, with helpers."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.officer_id, self.officer = org.user("rti-officer")
        self.custodian_id, self.custodian = org.user("rti-custodian")
        self.appellate_id, self.appellate = org.user("rti-appellate-authority")
        self.viewer_id, self.viewer = org.user("rti-viewer")

    @staticmethod
    def ok(response):
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json()

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(BASE + path, headers=headers or self.officer)

    def post(self, path: str, body=None, headers: dict | None = None):
        return self.client.post(BASE + path, json=body, headers=headers or self.officer)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(BASE + path, json=body, headers=headers or self.officer)

    def request(self, **over) -> dict:
        body = {
            "received_via": "post",
            "received_on": days(0),
            "applicant": dict(APPLICANT),
            "subject": "Admission records of 2025",
            "information_sought": "Copies of the merit list and the cut-off marks.",
            "fee": {"status": "paid", "amount": {"amount": "10.00", "currency": "INR"}, "mode": "cash"},
        }
        body.update(over)
        return self.ok(self.post("/requests", body))

    def assigned(self, **over) -> dict:
        r = self.request(**over)
        return self.ok(self.post(f"/requests/{r['id']}/assign", {"officer_id": self.officer_id}))

    def respond(self, request_id: str, **over) -> dict:
        body = {
            "type": "information_provided",
            "summary": "Copies enclosed.",
            "dispatched_on": days(0),
            "dispatch_mode": "post",
        }
        body.update(over)
        return self.ok(self.post(f"/requests/{request_id}/respond", body))

    def responded(self, received_on: str | None = None, **over) -> dict:
        r = self.assigned(**({"received_on": received_on} if received_on else {}))
        return self.respond(r["id"], **over)

    def appealed(self) -> dict:
        r = self.responded()
        body = {"filed_on": days(0), "grounds": "The information is incomplete."}
        return self.ok(self.post(f"/requests/{r['id']}/appeal", body, self.appellate))


@pytest.fixture
def desk(client, org, clock, settings) -> Desk:
    """A desk with response, appeal window and appeal decision all set to 30 calendar days."""
    settings(response_days=30, appeal_window_days=30, appeal_decide_days=30)
    return Desk(client, org)
