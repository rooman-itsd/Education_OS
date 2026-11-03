"""The module's tests run alone: only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file."""

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp().replace('\\', '/')}/selection_process_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import init_db
from eos_core.security import create_token
from eos_selection_process.api.router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
BASE = "/api/v1/selection-process"


def new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


class Org:
    """One organisation with helpers to mint users holding module roles."""

    def __init__(self) -> None:
        self.id = new_id()

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        uid = user_id or new_id()
        token = create_token(user_id=uid, organisation_id=self.id, roles=list(roles))
        return uid, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org() -> Org:
    return Org()


@pytest.fixture
def other_org() -> Org:
    return Org()
