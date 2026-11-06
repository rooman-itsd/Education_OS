"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/productions_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import init_db, new_id
from eos_core.security import create_token
from eos_productions.api.router import router
from eos_productions.application import service
from fastapi import FastAPI
from fastapi.testclient import TestClient

# A Monday morning; every test schedules relative to it.
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
BASE = "/api/v1/productions"

COORDINATOR = "productions-coordinator"
LEAD = "productions-lead"
MEMBER = "productions-member"


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
    """One organisation with helpers to mint users holding module roles."""

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


def days(n: float) -> str:
    """An ISO instant n days after NOW."""
    return (NOW + timedelta(days=n)).isoformat()


def make_production(client, headers, **overrides) -> dict:
    body = {"title": "Twelfth Night", "kind": "performance", **overrides}
    r = client.post(f"{BASE}/productions", json=body, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()
