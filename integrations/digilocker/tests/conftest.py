import os
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))

import pytest
from dgl_support import NOW, Org, fixed_clock
from eos_core.db import SessionLocal, init_db
from eos_digilocker.api.router import router
from eos_digilocker.application.adapter import DigiLockerAdapter
from eos_digilocker.application.runtime import Runtime
from eos_digilocker.domain import models  # noqa: F401  registers the tables
from eos_digilocker.infrastructure.documents import InMemoryDocuments
from eos_digilocker.infrastructure.mock import MockDigiLocker
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """The adapter alone: no other module is needed for its tests to pass (module standard)."""
    init_db()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/digilocker")
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def adapter_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("DIGILOCKER_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DIGILOCKER_SANDBOX_BASE_URL", "https://sandbox.digilocker.invalid/public")
    monkeypatch.setenv("DIGILOCKER_REQUESTER_CLIENT_ID", "REQ-APP-001")
    monkeypatch.setenv("DIGILOCKER_REQUESTER_CLIENT_SECRET", "requester-secret-fixture")
    monkeypatch.setenv("DIGILOCKER_SANDBOX_REQUESTER_CLIENT_ID", "REQ-APP-001")
    monkeypatch.setenv("DIGILOCKER_SANDBOX_REQUESTER_CLIENT_SECRET", "requester-secret-fixture")
    monkeypatch.setenv("DIGILOCKER_SEARCH_KEY_PEPPER", "test-pepper")


@pytest.fixture
def documents():
    return InMemoryDocuments()


@pytest.fixture
def mock():
    m = MockDigiLocker(strict=True, clock=fixed_clock)
    m.register_client("PUSH-APP-001", "push-secret-fixture")
    m.register_client("REQ-APP-001", "requester-secret-fixture")
    return m


@pytest.fixture
def adapter(documents, mock, client):
    return DigiLockerAdapter(Runtime(session_factory=SessionLocal, documents=documents, mock=mock, clock=fixed_clock))


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()


@pytest.fixture
def now():
    return NOW
