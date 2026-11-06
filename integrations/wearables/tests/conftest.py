"""Fixtures only. Everything the tests share lives in wear_support.py, imported by a unique name rather than from
`conftest`, which in a combined run can be another module's."""

import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/wearables_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))  # every permissions.yaml

import httpx
import pytest
from wear_support import POLAR_KEY, STRAVA_SUB, STRAVA_VERIFY, Clock, Transport


@pytest.fixture(scope="session", autouse=True)
def database():
    from eos_core.db import init_db
    from eos_wearables.infrastructure import models  # noqa: F401  registers the tables

    init_db()


@pytest.fixture(autouse=True)
def clean_tables(database):
    """Every test starts from empty tables: provider ids in the fixtures are fixed, so rows must not carry over."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_wearables.infrastructure.models import TABLES

    yield
    with platform_scope(), SessionLocal() as db:
        for t in reversed(TABLES):
            db.execute(t.delete())
        db.commit()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may open a socket: a client built without a MockTransport fails loudly."""

    def refuse(self, request):
        raise AssertionError(f"a test tried to reach the network: {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("WEARABLES_"):
            monkeypatch.delenv(k)
    for k, v in {
        "GARMIN_CLIENT_ID": "platform-garmin-id", "GARMIN_CLIENT_SECRET": "platform-garmin-secret",
        "POLAR_CLIENT_ID": "platform-polar-id", "POLAR_CLIENT_SECRET": "platform-polar-secret", "POLAR_WEBHOOK_SIGNATURE_KEY": POLAR_KEY,
        "GOOGLE_HEALTH_CLIENT_ID": "platform-google-id", "GOOGLE_HEALTH_CLIENT_SECRET": "platform-google-secret",
        "GOOGLE_HEALTH_API_BASE_URL": "https://health.example/v1", "GOOGLE_HEALTH_SCOPES": "https://example.invalid/auth/health.read",
        "STRAVA_CLIENT_ID": "platform-strava-id", "STRAVA_CLIENT_SECRET": "platform-strava-secret", "STRAVA_VERIFY_TOKEN": STRAVA_VERIFY,
        "STRAVA_SUBSCRIPTION_ID": STRAVA_SUB,
    }.items():  # fmt: skip
        monkeypatch.setenv("WEARABLES_" + k, v)
    from eos_wearables.infrastructure.providers import strava

    strava._BLOCKED.clear()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def transport():
    t = Transport()
    yield t
    assert not t.unexpected, f"requests nothing routed: {t.unexpected}"


@pytest.fixture
def adapter(transport, clock, monkeypatch):
    from eos_wearables.api import router as router_module
    from eos_wearables.application.adapter import WearablesAdapter

    monkeypatch.setattr(router_module, "clock", clock)  # restored after the test
    return WearablesAdapter(client_factory=transport.factory(), clock=clock)


@pytest.fixture
def client(clock, monkeypatch):
    """The alerts API alone, as module-standard rule 6 asks: no host and no other module. It reads the same fixed
    clock as the test data (wear_support.NOW), so an alert's age never depends on today's date or on which test
    ran before."""
    from eos_wearables.api import router as router_module
    from eos_wearables.api.router import router

    monkeypatch.setattr(router_module, "clock", clock)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from wear_support import PREFIX

    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def org():
    from wear_support import Org

    return Org()


@pytest.fixture
def other_org():
    from wear_support import Org

    return Org()
