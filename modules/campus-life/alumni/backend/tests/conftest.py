import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/alumni_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))  # every permissions.yaml

import pytest
from al_support import BASE, Clock, Org


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard)."""
    from eos_alumni.api.router import router
    from eos_alumni.infrastructure import models  # noqa: F401  registers the tables
    from eos_core.db import init_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    from eos_alumni.application import service

    fake = Clock()
    monkeypatch.setattr(service, "clock", fake)
    return fake


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
