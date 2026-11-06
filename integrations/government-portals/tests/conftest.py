"""Fixtures only. Helpers live in gp_support.py, so test files import them by a unique name rather than from
`conftest`, which in a combined run can be another module's."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))

import pytest
from eos_core.db import init_db
from eos_government_portals.api.router import router
from eos_government_portals.application.adapter import GovernmentPortalsAdapter
from eos_government_portals.domain import models  # noqa: F401  registers the tables
from eos_government_portals.infrastructure.documents import MemoryDocumentStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gp_support import PREFIX, Org


@pytest.fixture(scope="session")
def client():
    """The adapter alone: no other module is needed for its tests to pass (module standard)."""
    init_db()
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def adapter_env(monkeypatch):
    for key in ("AISHE_FORMAT", "NIRF_FORMAT", "NAAC_FORMAT", "MAX_EVIDENCE_FILE_BYTES", "MAX_PACKAGE_BYTES"):
        monkeypatch.delenv(f"GOVERNMENT_PORTALS_{key}", raising=False)


@pytest.fixture
def docs():
    return MemoryDocumentStore()


@pytest.fixture
def adapter(client, docs):
    return GovernmentPortalsAdapter(documents=docs)


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
