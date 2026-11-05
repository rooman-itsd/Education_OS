"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/library_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_library.api.router import router
from eos_library.application import service
from eos_library.infrastructure.models import new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# A Thursday morning; every test works relative to it.
NOW = datetime(2026, 10, 29, 8, 0, tzinfo=UTC)
BASE = "/api/v1/library"
STUDENT_POLICY = {
    "member_category": "student",
    "max_loans": 2,
    "loan_days": 14,
    "max_renewals": 1,
    "fine_per_day": "2.00",
    "max_unpaid_fines": "10.00",
    "hold_days": 3,
}


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


@pytest.fixture
def tick(monkeypatch):
    """Move the clock forward by minutes, so things done one after another get distinct times."""

    def go(minutes: int):
        monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(minutes=minutes))

    return go


@pytest.fixture
def travel(monkeypatch):
    """Move the clock forward by whole days."""

    def go(days: int):
        monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(days=days))
        return NOW + timedelta(days=days)

    return go


class Org:
    """One organisation with helpers to mint users holding library or profile roles."""

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


class Library:
    """An organisation's library with a head librarian, a desk librarian, a viewer and a student loan policy."""

    def __init__(self, client, org: Org) -> None:
        self.client, self.org = client, org
        _, self.admin = org.user("library-admin")
        self.librarian_id, self.librarian = org.user("librarian")
        _, self.viewer = org.user("library-viewer")
        r = client.put(f"{BASE}/loan-policies", json=[STUDENT_POLICY], headers=self.admin)
        assert r.status_code == 200, r.text
        self._n = 0

    def post(self, path: str, body, headers: dict):
        return self.client.post(f"{BASE}{path}", json=body, headers=headers)

    def get(self, path: str, headers: dict):
        return self.client.get(f"{BASE}{path}", headers=headers)

    def patch(self, path: str, body, headers: dict):
        return self.client.patch(f"{BASE}{path}", json=body, headers=headers)

    def title(self, name: str = "Gray's Anatomy", copies: int = 1, **extra) -> tuple[dict, list[str]]:
        """Catalogue a title with copies; returns (title, barcodes)."""
        t = self.post("/titles", {"title": name, "kind": "book", **extra}, self.librarian)
        assert t.status_code == 201, t.text
        barcodes = []
        for _ in range(copies):
            self._n += 1
            code = f"BC-{self.org.id[:6]}-{self._n:04d}"
            c = self.post(
                f"/titles/{t.json()['id']}/copies",
                {"accession_no": f"ACC-{self._n:05d}", "barcode": code},
                self.librarian,
            )
            assert c.status_code == 201, c.text
            barcodes.append(code)
        return t.json(), barcodes

    def student(self, category: str = "student") -> tuple[str, dict]:
        """A student who is a library member; returns (person_id, headers)."""
        person_id, headers = self.org.user("student")
        r = self.post("/members", {"person_id": person_id, "category": category}, self.librarian)
        assert r.status_code == 201, r.text
        return person_id, headers

    def issue(self, barcode: str, person_id: str):
        return self.post("/loans", {"barcode": barcode, "person_id": person_id}, self.librarian)

    def give_back(self, barcode: str, **extra):
        return self.post("/returns", {"barcode": barcode, **extra}, self.librarian)


@pytest.fixture
def lib(client, org) -> Library:
    return Library(client, org)


def events(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(OutboxEvent.occurred_at)
        )
        return [r.payload for r in rows]
