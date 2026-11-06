"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it. Helpdesk events are delivered
through the registered handlers (deliver), with payloads shaped as helpdesk's contracts/events.yaml describes them;
no clock row is inserted by hand."""

import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/sla_management_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/sla-management"
# Monday 2 November 2026, 09:00 UTC
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
CATEGORY = "22222222-2222-4222-8222-222222222222"
OTHER_CATEGORY = "33333333-3333-4333-8333-333333333333"
QUEUE = "44444444-4444-4444-8444-444444444444"
LEAD = "55555555-5555-4555-8555-555555555555"


def new_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_sla_management.api.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tables():
    """The tables, for tests that deliver events without the API."""
    import eos_sla_management.infrastructure.models  # noqa: F401
    from eos_core.db import init_db

    init_db()


@pytest.fixture
def clock(monkeypatch):
    """The service's clock, frozen at NOW; tests move it with clock.set()."""
    from eos_sla_management.application import service

    class Clock:
        now = NOW

        def set(self, value: datetime) -> None:
            self.now = value

    frozen = Clock()
    monkeypatch.setattr(service, "clock", lambda: frozen.now)
    return frozen


class Org:
    """One organisation with helpers to mint users holding module roles."""

    def __init__(self) -> None:
        self.id = new_uuid()

    def user(self, *roles: str) -> tuple[str, dict]:
        from eos_core.security import create_token

        user_id = new_uuid()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org() -> Org:
    return Org()


@pytest.fixture
def other_org() -> Org:
    return Org()


@dataclass(frozen=True)
class FakeEvent:
    """The envelope platform/event-bus hands a consumer (eos_event_bus.domain.models.Event)."""

    name: str
    organisation_id: str | None
    payload: object
    id: str = field(default_factory=new_uuid)
    version: int = 1
    actor: str | None = None
    occurred_at: datetime = NOW


def deliver(organisation_id: str | None, name: str, payload, **envelope) -> str:
    """Deliver one helpdesk event as the relay does: the handler in the event's organisation, its own session, a
    commit afterwards."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope
    from eos_sla_management.application.consumers import CONSUMERS

    event = envelope.pop("event", None) or FakeEvent(
        name=name, organisation_id=organisation_id, payload=payload, **envelope
    )
    with organisation_scope(event.organisation_id), SessionLocal() as db:
        result = CONSUMERS[name](db, event)
        db.commit()
    return result


def at(minutes: int) -> str:
    """NOW plus minutes, as an ISO date-time with offset, as helpdesk publishes it."""
    return (NOW + timedelta(minutes=minutes)).isoformat()


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
    """Actions of the audit entries for one entity, in order of time."""
    from eos_core.db import SessionLocal
    from eos_sla_management.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.action)
        )
        return [r.action for r in rows]


def calendar_body(**over) -> dict:
    body = {"name": "Round the clock", "time_zone": "UTC", "always_open": True}
    body.update(over)
    return body


OFFICE_HOURS = [{"weekday": d, "start": "09:00", "end": "17:00"} for d in range(1, 6)]


def policy_body(calendar_id: str, **over) -> dict:
    body = {
        "name": "High priority",
        "priority": "high",
        "category_id": None,
        "calendar_id": calendar_id,
        "response_target_minutes": 60,
        "resolution_target_minutes": 240,
        "warning_percent": 50,
        "escalation_levels": [
            {"level": 1, "after_breach_minutes": 0, "notify_assignee": True, "notify_person_ids": []},
            {"level": 2, "after_breach_minutes": 60, "notify_assignee": False, "notify_person_ids": [LEAD]},
        ],
    }
    body.update(over)
    return body


class Desk:
    """An organisation with an admin, a viewer and an agent (a viewer too). Setup goes through the HTTP API; tickets
    through helpdesk's events."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.admin_id, self.admin = org.user("sla-management-admin")
        self.viewer_id, self.viewer = org.user("sla-management-viewer")
        self.agent_id, self.agent = org.user("sla-management-viewer")

    @staticmethod
    def ok(response):
        assert response.status_code in (200, 201), response.text
        return response.json()

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(f"{BASE}{path}", headers=headers or self.admin)

    def post(self, path: str, body, headers: dict | None = None):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers or self.admin)

    def calendar(self, **over) -> dict:
        return self.ok(self.post("/calendars", calendar_body(**over)))

    def policy(self, calendar_id: str | None = None, **over) -> dict:
        calendar_id = calendar_id or self.calendar()["id"]
        return self.ok(self.post("/policies", policy_body(calendar_id, **over)))

    def send(self, name: str, payload: dict, **envelope) -> str:
        return deliver(self.org.id, f"helpdesk.ticket.{name}", payload, **envelope)

    def ticket(self, *, priority: str = "high", category_id: str = CATEGORY, created: int = 0, number: str = "") -> str:
        """A helpdesk ticket created `created` minutes after NOW; its id."""
        ticket_id = new_uuid()
        self.send(
            "created",
            {
                "organisation_id": self.org.id,
                "ticket_id": ticket_id,
                "number": number or f"HD-{ticket_id[:6]}",
                "requester_id": new_uuid(),
                "raised_by_id": new_uuid(),
                "channel": "portal",
                "category_id": category_id,
                "queue_id": QUEUE,
                "priority": priority,
                "created_at": at(created),
            },
        )
        return ticket_id

    def assign(self, ticket_id: str, assignee_id: str | None, minutes: int = 1) -> str:
        return self.send(
            "assigned",
            {
                "organisation_id": self.org.id,
                "ticket_id": ticket_id,
                "number": "HD-1",
                "queue_id": QUEUE,
                "previous_queue_id": None,
                "assignee_id": assignee_id,
                "previous_assignee_id": None,
                "assigned_by": new_uuid(),
            },
            occurred_at=NOW + timedelta(minutes=minutes),
        )

    def clocks(self, ticket_id: str) -> dict[str, dict]:
        body = self.ok(self.get(f"/tickets/{ticket_id}", self.viewer))
        return {c["kind"]: c for c in body["clocks"]}


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)
