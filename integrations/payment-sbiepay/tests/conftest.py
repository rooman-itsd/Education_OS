import os
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))

import httpx
import pytest
from eos_core.db import init_db
from eos_payment_sbiepay.api.router import router
from eos_payment_sbiepay.domain import models  # noqa: F401  registers the tables
from eos_payment_sbiepay.infrastructure import notifier
from eos_payment_sbiepay.infrastructure.gateway import MockGateway
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sbiepay_support import NOTIFY_SECRET, PREFIX, Org


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
    for key in ("MERCHANT_ID", "ALLOWED_RETURN_HOSTS", "CALLBACK_BASE_URL"):
        monkeypatch.delenv(f"PAYMENT_SBIEPAY_{key}", raising=False)
    monkeypatch.setenv("PAYMENT_SBIEPAY_MODE", "mock")
    monkeypatch.setenv("PAYMENT_SBIEPAY_NOTIFY_SECRET", NOTIFY_SECRET)
    MockGateway.reset()


class Receiver:
    """Captures signed notifications; answers with `status` (200 by default)."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status)


@pytest.fixture(autouse=True)
def receiver(monkeypatch):
    r = Receiver()
    monkeypatch.setattr(notifier, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(r.handler)))
    return r


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
