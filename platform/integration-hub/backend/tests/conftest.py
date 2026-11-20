"""The hub alone: its own tables, identity's (who is calling) and audit's (a declared dependency), the outbox, and a
test-only adapter found through the real entry-point group. No network: the adapter answers from tests/fixtures."""

import base64
import os
import sys
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/integration_hub_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))  # every permissions.yaml
sys.path.insert(0, str(Path(__file__).resolve().parent / "fake_adapter"))  # hub_fake_adapter and its entry point

import pytest
from hub_support import BASE, Clock, Org, SuperAdmin


def _hub_env(monkeypatch, secret_dir: str) -> None:
    for key in list(os.environ):
        if key.startswith("INTEGRATION_HUB_") or key.startswith("FAKE_ADAPTER_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_BACKEND", "file")
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_DIR", secret_dir)
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_KEK", base64.b64encode(b"k" * 32).decode())
    monkeypatch.setenv("INTEGRATION_HUB_ALLOW_MOCK", "true")
    # only the test adapter, whatever else the environment installed on the entry point group
    monkeypatch.setenv("INTEGRATION_HUB_ADAPTERS", "fake-adapter")
    monkeypatch.setenv("INTEGRATION_HUB_ALLOWED_RETURN_HOSTS", "app.example.test")
    monkeypatch.setenv("INTEGRATION_HUB_PUBLIC_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("FAKE_ADAPTER_APP_KEY", "app-level-signing-key")
    monkeypatch.setenv("FAKE_ADAPTER_VERIFY_TOKEN", "verify-me")


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard)."""
    from eos_audit.domain import models as audit_models  # noqa: F401  registers audit_record
    from eos_core.db import init_db
    from eos_identity.domain import models as identity_models  # noqa: F401  registers identity_user
    from eos_integration_hub.api.router import router
    from eos_integration_hub.infrastructure import models  # noqa: F401  registers the tables
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def hub_env(monkeypatch, tmp_path):
    import hub_fake_adapter
    from eos_integration_hub.infrastructure import registry

    _hub_env(monkeypatch, str(tmp_path / "secrets"))
    hub_fake_adapter.reset()
    registry.reset_cache()
    yield tmp_path / "secrets"
    registry.reset_cache()


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    from eos_integration_hub.application import common

    fake = Clock()
    for mod in _clock_users():
        monkeypatch.setattr(mod, "clock", fake)
    monkeypatch.setattr(common, "clock", fake)
    return fake


def _clock_users():
    from eos_integration_hub.application import (
        authorisation,
        catalogue,
        connections,
        deliveries,
        health,
        inbound,
    )

    return (authorisation, catalogue, connections, deliveries, health, inbound)


@pytest.fixture
def org(client):
    return Org()


@pytest.fixture
def other_org(client):
    return Org()


@pytest.fixture
def super_admin(client):
    return SuperAdmin()


@pytest.fixture
def adapter():
    import hub_fake_adapter

    return hub_fake_adapter


@pytest.fixture(autouse=True)
def _clean_queue(client):
    """The sweep and the token refresh act on every organisation, so one test's rows must not be worked off by the
    next. Only the queue and links are cleared; connections stay, each test uses fresh organisations."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_integration_hub.infrastructure.models import AccountLink, Delivery, DeliveryAttempt, InboundReceipt
    from sqlalchemy import delete, update

    with platform_scope(), SessionLocal() as db:
        db.execute(delete(DeliveryAttempt))
        db.execute(delete(Delivery))
        db.execute(delete(InboundReceipt))
        db.execute(update(AccountLink).values(expires_at=None))
        db.commit()
