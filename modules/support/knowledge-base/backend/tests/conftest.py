"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database is
always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core.

FastAPI is imported inside the API fixtures, so the domain tests run without it."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/knowledge_base_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest

BASE = "/api/v1/knowledge-base"
NOW = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
TODAY = NOW.date()


@pytest.fixture(scope="session")
def client():
    from eos_core.db import init_db
    from eos_knowledge_base.api.router import router
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
    from eos_knowledge_base.application import service

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
    from eos_knowledge_base.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.organisation_id == organisation_id, AuditEntry.entity_id == entity_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(r.action, r.reason) for r in rows]


class Desk:
    """An organisation's knowledge base: an editor, two authors, a reader and a viewer, with request helpers."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        self.editor_id, self.editor = org.user("knowledge-base-editor")
        self.author_id, self.author = org.user("knowledge-base-author")
        self.author2_id, self.author2 = org.user("knowledge-base-author")
        self.reader_id, self.reader = org.user("knowledge-base-reader")
        self.viewer_id, self.viewer = org.user("knowledge-base-viewer")
        self._category: str | None = None

    @staticmethod
    def ok(response):
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json()

    def get(self, path: str, headers: dict | None = None):
        return self.client.get(BASE + path, headers=headers or self.editor)

    def post(self, path: str, body=None, headers: dict | None = None):
        return self.client.post(BASE + path, json=body, headers=headers or self.editor)

    def patch(self, path: str, body, headers: dict | None = None):
        return self.client.patch(BASE + path, json=body, headers=headers or self.editor)

    def put(self, path: str, body=None, headers: dict | None = None):
        return self.client.put(BASE + path, json=body, headers=headers or self.editor)

    def category(self, name: str = "IT", **over) -> dict:
        return self.ok(self.post("/categories", {"name": name, **over}))

    @property
    def category_id(self) -> str:
        if self._category is None:
            self._category = self.category(f"General {self.org.id[:8]}")["id"]
        return self._category

    def body(self, **over) -> dict:
        body = {
            "type": "how_to",
            "title": "Connect to campus Wi-Fi",
            "summary": "Join the campus network on a laptop or phone",
            "body": "1. Open Wi-Fi settings.\n2. Choose CAMPUS.\n3. Sign in with your portal password.",
            "category_id": self.category_id,
            "tags": ["wifi", "network"],
            "audience": "everyone",
        }
        body.update(over)
        return body

    def draft(self, headers: dict | None = None, **over) -> dict:
        return self.ok(self.post("/articles", self.body(**over), headers or self.author))

    def published(self, **over) -> dict:
        article = self.draft(**over)
        return self.ok(self.post(f"/articles/{article['id']}/publish", {}))


@pytest.fixture
def desk(client, org, clock) -> Desk:
    return Desk(client, org)


def days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()
