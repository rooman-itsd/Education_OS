import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/fees_accounts_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))  # every permissions.yaml

import httpx
import pytest
from fees_support import BASE, NOW, Org


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard)."""
    from eos_core.db import init_db
    from eos_fees_accounts.api.router import router
    from eos_fees_accounts.infrastructure import models  # noqa: F401  registers the tables
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    from eos_fees_accounts.application import service

    monkeypatch.setattr(service, "clock", lambda: NOW)
    for key in ("PAYMENT_ADAPTER_URL", "PAYMENT_RETURN_URL", "ACADEMIC_YEAR_START_MONTH", "FINE_DUE_DAYS"):
        monkeypatch.delenv(f"FEES_ACCOUNTS_{key}", raising=False)


class Adapter:
    """Stands in for payment-sbiepay: records requests and answers with `status` and `body`."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.status = 201
        self.body: dict = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


@pytest.fixture
def adapter(monkeypatch):
    from eos_fees_accounts.infrastructure import payment_adapter

    a = Adapter()
    monkeypatch.setenv("FEES_ACCOUNTS_PAYMENT_ADAPTER_URL", "https://api.example.com/api/v1/payment-sbiepay")
    monkeypatch.setenv("FEES_ACCOUNTS_PAYMENT_RETURN_URL", "https://college.example.com/fees")
    monkeypatch.setattr(
        payment_adapter, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(a.handler))
    )
    return a


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
