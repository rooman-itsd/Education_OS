"""Helpers shared by the budget-grants tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/budget-grants"
NOW = datetime(2026, 10, 23, 9, 30, tzinfo=UTC)
TODAY = NOW.date().isoformat()
YEAR = "2026-27"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with one user per role."""

    ROLES = {
        "staff": ["finance-staff"],
        "manager": ["management"],
        "research": ["research-office"],
        "admin": ["org-admin"],
        "dept": ["department-admin"],
        "faculty": ["faculty"],
        "scholar": ["research-scholar"],
        "nobody": [],
    }

    def __init__(self):
        self.id = new_id()
        self.ids: dict[str, str] = {}
        self.headers: dict[str, dict] = {}
        for name, roles in self.ROLES.items():
            uid = new_id()
            self.ids[name] = uid
            self.headers[name] = auth(create_token(user_id=uid, organisation_id=self.id, roles=roles))

    def __getattr__(self, name: str) -> dict:
        try:
            return self.__dict__["headers"][name]
        except KeyError as e:
            raise AttributeError(name) from e

    def token(self, who: str) -> str:
        return self.headers[who]["Authorization"].split(" ", 1)[1]


def head(client, org: Org, code: str | None = None, name: str | None = None) -> dict:
    code = code or f"H{new_id()[:6].upper()}"
    r = client.post(f"{BASE}/budget-heads", json={"code": code, "name": name or code.title()}, headers=org.staff)
    assert r.status_code == 201, r.text
    return r.json()


def approved_budget(client, org: Org, allocations: dict | None = None, year: str = YEAR, department_id=None) -> dict:
    """An approved budget; `allocations` maps head dicts' ids to amounts."""
    if allocations is None:
        allocations = {head(client, org)["id"]: "100000.00"}
    body = {
        "financial_year": year,
        "department_id": department_id,
        "title": "Physics" if department_id else "Institution",
        "lines": [{"budget_head_id": h, "allocated": a} for h, a in allocations.items()],
    }
    r = client.post(f"{BASE}/budgets", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    b = r.json()
    assert client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff).status_code == 200
    r = client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200, r.text
    return r.json()


def grant(client, org: Org, pi: str = "faculty", amount: str = "500000.00", **overrides) -> dict:
    h1, h2 = head(client, org), head(client, org)
    half = f"{float(amount) / 2:.2f}"
    body = {
        "code": f"G-{new_id()[:8]}",
        "title": "Soil microbiome study",
        "funder": "DST",
        "scheme": "SERB Core",
        "sanctioned_amount": amount,
        "start_date": "2026-04-01",
        "end_date": "2028-03-31",
        "investigators": [
            {"user_id": org.ids[pi], "role": "principal"},
            {"user_id": org.ids["scholar"], "role": "co_investigator"},
        ],
        "lines": [{"budget_head_id": h1["id"], "sanctioned": half}, {"budget_head_id": h2["id"], "sanctioned": half}],
        **overrides,
    }
    r = client.post(f"{BASE}/grants", json=body, headers=org.research)
    assert r.status_code == 201, r.text
    return r.json()


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]
