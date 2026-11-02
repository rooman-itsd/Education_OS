"""Helpers shared by the hr-payroll tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/hr-payroll"
NOW = datetime(2026, 10, 28, 9, 30, tzinfo=UTC)  # 15:00 on 28 October in India
TODAY = "2026-10-28"
ACCOUNT = "123456789012"
PAN = "ABCDE1234F"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with one user per role."""

    ROLES = {
        "hr": ["hr-staff"],
        "hr2": ["hr-staff"],
        "finance": ["finance-staff"],
        "manager": ["management"],
        "dept": ["department-admin"],
        "faculty": ["faculty"],
        "faculty2": ["faculty"],
        "admin": ["org-admin"],
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


def employee(client, org: Org, who: str | None = "faculty", **fields) -> dict:
    """An employee added by HR; `who` is the org user linked to it (None for no user)."""
    body = {
        "employee_code": f"E{new_id()[:8]}",
        "name": f"Employee {new_id()[:4]}",
        "email": "someone@example.com",
        "joined_on": "2024-06-01",
        "employment_type": "permanent",
        "staff_category": "teaching",
        "designation": "Assistant Professor",
        "department_id": None,
        "user_id": org.ids[who] if who else None,
        "bank_account": {"account_holder": "Someone", "account_number": ACCOUNT, "ifsc": "SBIN0001234"},
        **fields,
    }
    r = client.post(f"{BASE}/employees", json=body, headers=org.hr)
    assert r.status_code == 201, r.text
    return r.json()


def salary(client, org: Org, e: dict, effective_from: str = "2024-06-01", lines=None, who: str = "hr") -> dict:
    lines = lines or [
        {"code": "BASIC", "name": "Basic", "kind": "earning", "amount": "30000.00"},
        {"code": "HRA", "name": "House rent", "kind": "earning", "amount": "12000.00"},
        {"code": "PF", "name": "Provident fund", "kind": "deduction", "amount": "3600.00"},
    ]
    r = client.put(
        f"{BASE}/employees/{e['id']}/salary",
        json={"effective_from": effective_from, "lines": lines},
        headers=org.headers[who],
    )
    assert r.status_code == 200, r.text
    return r.json()


def leave_type(client, org: Org, code: str = "CL", days=12, paid=True, **fields) -> dict:
    body = {"code": code, "name": f"{code} leave", "days_per_year": days, "paid": paid, **fields}
    r = client.post(f"{BASE}/leave-types", json=body, headers=org.hr)
    assert r.status_code == 201, r.text
    return r.json()


def apply(client, org: Org, who: str, t: dict, start: str, end: str, **fields):
    body = {"leave_type_id": t["id"], "from": start, "to": end, **fields}
    return client.post(f"{BASE}/leave-requests", json=body, headers=org.headers[who])


def decide(client, org: Org, request_id: str, decision: str = "approved", who: str = "hr"):
    return client.post(
        f"{BASE}/leave-requests/{request_id}/decision", json={"decision": decision}, headers=org.headers[who]
    )


def start_run(client, org: Org, period: str = "2026-10", who: str = "hr"):
    return client.post(f"{BASE}/payroll-runs", json={"period": period}, headers=org.headers[who])


def approved_run(client, org: Org, period: str = "2026-10") -> dict:
    run = start_run(client, org, period).json()
    assert client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr).status_code == 200
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=org.finance)
    assert r.status_code == 200, r.text
    return r.json()


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]
