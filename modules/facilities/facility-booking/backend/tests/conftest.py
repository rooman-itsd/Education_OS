"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/facility_booking_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))
os.environ["FACILITY_BOOKING_TIMEZONE"] = "UTC"

import pytest
from eos_core.db import init_db
from eos_core.security import create_token
from eos_facility_booking.api.router import router
from eos_facility_booking.application import service
from eos_facility_booking.infrastructure.models import new_id
from fastapi import FastAPI
from fastapi.testclient import TestClient

# A Monday morning; every test books relative to it.
NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
BASE = "/api/v1/facility-booking"


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


def at(hour: int, minute: int = 0, day: int = 12) -> str:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC).isoformat()
