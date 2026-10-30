"""Helpers shared by the procurement tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/procurement"
NOW = datetime(2026, 10, 28, 9, 30, tzinfo=UTC)
TODAY = NOW.date().isoformat()
LATER = (NOW + timedelta(days=7)).isoformat()
BUDGET_URL = "http://budget-grants.test/api/v1/budget-grants"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with one user per role."""

    ROLES = {
        "staff": ["finance-staff"],
        "staff2": ["finance-staff"],
        "manager": ["management"],
        "manager2": ["management"],
        "dept": ["department-admin"],
        "facility": ["facility-staff"],
        "faculty": ["faculty"],
        "research": ["research-office"],
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
        self.line = new_id()  # a budget-grants line of this organisation

    def __getattr__(self, name: str) -> dict:
        try:
            return self.__dict__["headers"][name]
        except KeyError as e:
            raise AttributeError(name) from e

    def token(self, who: str) -> str:
        return self.headers[who]["Authorization"].split(" ", 1)[1]


def item(quantity=10, unit_price: str | None = "100.00", tax_percent=None, description="Beaker 250 ml") -> dict:
    out = {"description": description, "quantity": quantity, "unit": "nos"}
    if unit_price is not None:
        out["unit_price"] = unit_price
    if tax_percent is not None:
        out["tax_percent"] = tax_percent
    return out


def vendor(client, org: Org, *, approved: bool = True, categories=("lab equipment",), **fields) -> dict:
    body = {"name": f"Vendor {new_id()[:6]}", "categories": list(categories), **fields}
    r = client.post(f"{BASE}/vendors", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    v = r.json()
    if approved:
        r = client.post(
            f"{BASE}/vendors/{v['id']}/status", json={"status": "approved", "reason": "checked"}, headers=org.staff
        )
        assert r.status_code == 200, r.text
        v = r.json()
    return v


def indent(client, org: Org, cost: str = "1000.00", who: str = "faculty", line: str | None = None, **fields) -> dict:
    body = {
        "title": "Glassware for the chemistry lab",
        "line_id": line or org.line,
        "items": [item(unit_price=None)],
        "estimated_cost": cost,
        **fields,
    }
    r = client.post(f"{BASE}/indents", json=body, headers=org.headers[who])
    assert r.status_code == 201, r.text
    return r.json()


def approved_indent(client, org: Org, cost: str = "1000.00", who: str = "faculty", line: str | None = None) -> dict:
    i = indent(client, org, cost, who, line)
    assert client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.headers[who]).status_code == 200
    r = client.post(f"{BASE}/indents/{i['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200, r.text
    return r.json()


def direct_order(client, org: Org, v: dict | None = None, items: list | None = None, **fields) -> dict:
    i = approved_indent(client, org)
    v = v or vendor(client, org)
    body = {
        "vendor_id": v["id"],
        "indent_ids": [i["id"]],
        "items": items or [item(10, "100.00", 18)],
        "delivery_by": (NOW + timedelta(days=14)).date().isoformat(),
        **fields,
    }
    r = client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    return r.json()


def issued_order(client, org: Org, **kwargs) -> dict:
    po = direct_order(client, org, **kwargs)
    assert client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff).status_code == 200
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200, r.text
    return r.json()


def receive(client, org: Org, po: dict, *lines, received_on: str = TODAY):
    items = [
        {"item_index": n, "received": rec, "accepted": acc, **({"rejection_reason": "broken"} if acc < rec else {})}
        for n, rec, acc in lines
    ]
    return client.post(
        f"{BASE}/purchase-orders/{po['id']}/goods-receipts",
        json={"received_on": received_on, "items": items},
        headers=org.facility,
    )


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]
