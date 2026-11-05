"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/iqac_accreditation_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/iqac-accreditation"
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
TODAY = NOW.date()


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_iqac_accreditation.api.router import router
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
    from eos_iqac_accreditation.application import service

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
    from sqlalchemy import select, text

    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(text("rowid"))
        )
        return [r.payload for r in rows]


def audit(organisation_id: str, entity_id: str) -> list[tuple[str, str | None]]:
    """(action, reason) of the audit entries for one entity, in the order they were written (SQLite rowid: the
    frozen clock gives every entry the same time)."""
    from eos_core.db import SessionLocal
    from eos_iqac_accreditation.infrastructure.models import AuditEntry
    from sqlalchemy import select, text

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(text("rowid"))
        )
        return [(r.action, r.reason) for r in rows]


def days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


class Desk:
    """An organisation's IQAC desk: a coordinator, two contributors and a viewer, with request helpers."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.coordinator_id, self.coordinator = org.user("iqac-accreditation-coordinator")
        self.alice_id, self.alice = org.user("iqac-accreditation-contributor")
        self.bob_id, self.bob = org.user("iqac-accreditation-contributor")
        self.viewer_id, self.viewer = org.user("iqac-accreditation-viewer")
        self._n = 0

    @staticmethod
    def ok(response):
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json() if response.status_code != 204 else None

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(BASE + path, headers=headers or self.coordinator)

    def post(self, path: str, body=None, headers: dict | None = None):
        return self.client.post(BASE + path, json=body, headers=headers or self.coordinator)

    def put(self, path: str, body, headers: dict | None = None):
        return self.client.put(BASE + path, json=body, headers=headers or self.coordinator)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(BASE + path, json=body, headers=headers or self.coordinator)

    def delete(self, path: str, headers: dict | None = None):
        return self.client.delete(BASE + path, headers=headers or self.coordinator)

    def framework(self, **over) -> dict:
        self._n += 1
        body = {"code": f"FW{self._n}", "name": "Test framework"}
        body.update(over)
        return self.ok(self.post("/frameworks", body))

    def metric(self, framework_id: str, **over) -> dict:
        self._n += 1
        body = {"code": f"M{self._n}", "title": "A metric", "kind": "quantitative", "criterion": "Criterion 1"}
        body.update(over)
        return self.ok(self.post(f"/frameworks/{framework_id}/metrics", body))

    def cycle(self, framework_id: str | None = None, **over) -> dict:
        body = {
            "framework_id": framework_id or self.framework()["id"],
            "name": "Annual quality report",
            "period_start": "2025-04-01",
            "period_end": "2026-03-31",
        }
        body.update(over)
        return self.ok(self.post("/cycles", body))

    def move(self, cycle_id: str, status: str, **extra) -> dict:
        return self.ok(self.post(f"/cycles/{cycle_id}/status", {"status": status, **extra}))

    def assign(self, cycle_id: str, *items: tuple[str, str, str]) -> list[dict]:
        """items are (metric_id, owner_id, due_on)."""
        body = {"assignments": [{"metric_id": m, "owner_id": o, "due_on": d} for m, o, d in items]}
        return self.ok(self.post(f"/cycles/{cycle_id}/assignments", body))

    def collecting(self) -> dict:
        """A collecting cycle with a quantitative metric assigned to alice and a qualitative one to bob."""
        framework = self.framework()
        quantitative = self.metric(framework["id"], code="Q1", kind="quantitative", unit="%")
        qualitative = self.metric(framework["id"], code="N1", kind="qualitative")
        cycle = self.cycle(framework["id"])
        self.move(cycle["id"], "collecting")
        q, n = self.assign(
            cycle["id"], (quantitative["id"], self.alice_id, days(10)), (qualitative["id"], self.bob_id, days(20))
        )
        return {"framework": framework, "cycle": cycle, "q": q, "n": n, "metrics": (quantitative, qualitative)}

    def submitted_q(self) -> dict:
        """collecting() with alice's response filled in and submitted."""
        c = self.collecting()
        self.ok(self.put(f"/responses/{c['q']['id']}", {"value": 42.5}, self.alice))
        self.ok(self.post(f"/responses/{c['q']['id']}/submit", None, self.alice))
        return c

    def action_item(self, **over) -> dict:
        body = {"title": "Revise the feedback form", "owner_id": self.alice_id, "due_on": days(10)}
        body.update(over)
        return self.ok(self.post("/action-items", body))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)
