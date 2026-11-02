import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/e_office_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))  # every permissions.yaml

import pytest
from eo_support import BASE, Clock, Org


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard)."""
    from eos_core.db import init_db
    from eos_e_office.api.router import router
    from eos_e_office.infrastructure import models  # noqa: F401  registers the tables
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    from eos_e_office.application import service

    fake = Clock()
    monkeypatch.setattr(service, "clock", fake)
    for priority in ("NORMAL", "URGENT", "IMMEDIATE"):
        monkeypatch.delenv(f"E_OFFICE_DEFAULT_DUE_DAYS_{priority}", raising=False)
    return fake


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
