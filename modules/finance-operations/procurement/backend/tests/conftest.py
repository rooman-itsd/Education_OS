import os
import tempfile
from decimal import Decimal
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/procurement_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))  # every permissions.yaml

import httpx
import pytest
from pc_support import BASE, BUDGET_URL, NOW, Org


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard). budget-grants is reached
    over HTTP, so the tests stand it in with an httpx mock (see the budget fixture)."""
    from eos_core.db import init_db
    from eos_procurement.api.router import router
    from eos_procurement.infrastructure import models  # noqa: F401  registers the tables
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


class BudgetGrants:
    """budget-grants as procurement sees it. GET /availability: every line can cover any amount unless `available`
    says otherwise; lines in `missing` are not open (404). GET /expenditures?kind=commitment lists a procurement
    commitment for each order id in `recorded`, `page_size` per page. `status` forces an answer to every request,
    `expenditures_status` only to the listing; `down` refuses connections."""

    def __init__(self):
        self.available: dict[str, Decimal] = {}
        self.missing: set[str] = set()
        self.recorded: set[str] = set()
        self.page_size = 200
        self.status: int | None = None
        self.expenditures_status: int | None = None
        self.down = False
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("refused", request=request)
        if self.status is not None:
            return httpx.Response(self.status, json={"detail": {"code": "forced"}})
        if request.url.path.endswith("/expenditures"):
            return self._expenditures(request)
        line, amount = request.url.params["line_id"], Decimal(request.url.params["amount"])
        if line in self.missing:
            return httpx.Response(404, json={"detail": {"code": "not_found"}})
        left = self.available.get(line, Decimal("1000000000"))
        return httpx.Response(200, json={"line_id": line, "available": f"{left:.2f}", "sufficient": amount <= left})

    def _expenditures(self, request: httpx.Request) -> httpx.Response:
        if self.expenditures_status is not None:
            return httpx.Response(self.expenditures_status, json={"detail": {"code": "forced"}})
        assert request.url.params["kind"] == "commitment"
        rows = [
            {"source": {"module": "procurement", "reference": ref}, "kind": "commitment"}
            for ref in sorted(self.recorded)
        ]
        rows.append({"source": {"module": "manual", "reference": ""}, "kind": "commitment"})
        start = int(request.url.params.get("cursor") or 0)
        end = start + self.page_size
        return httpx.Response(
            200, json={"items": rows[start:end], "next_cursor": str(end) if end < len(rows) else None}
        )


@pytest.fixture(autouse=True)
def budget(monkeypatch):
    from eos_procurement.infrastructure import budget_grants

    fake = BudgetGrants()
    monkeypatch.setattr(budget_grants, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(fake)))
    return fake


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    from eos_procurement.application import service

    monkeypatch.setattr(service, "clock", lambda: NOW)
    monkeypatch.setenv("PROCUREMENT_BUDGET_GRANTS_URL", BUDGET_URL)
    monkeypatch.setenv("PROCUREMENT_DIRECT_PURCHASE_LIMIT", "50000")
    monkeypatch.setenv("PROCUREMENT_QUOTATION_LIMIT", "500000")
    monkeypatch.delenv("PROCUREMENT_INVOICE_MATCH_TOLERANCE_PERCENT", raising=False)


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
