import os
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_nad.api.router import router
from eos_nad.application.adapter import NadAdapter
from eos_nad.application.runtime import Runtime
from eos_nad.domain import models  # noqa: F401  registers the tables
from eos_nad.infrastructure.documents import InMemoryDocuments
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nad_support import NOW, Org, fixed_clock


@pytest.fixture(scope="session")
def client():
    """The adapter alone: no other module is needed for its tests to pass (module standard)."""
    init_db()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/nad")
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def adapter_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("NAD_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NAD_APAAR_HASH_PEPPER", "test-pepper")


@pytest.fixture
def documents():
    return InMemoryDocuments()


@pytest.fixture
def adapter(documents, client):
    return NadAdapter(Runtime(session_factory=SessionLocal, documents=documents, clock=fixed_clock))


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()


@pytest.fixture
def now():
    return NOW
