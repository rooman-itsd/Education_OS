"""Helpers shared by the fees-accounts tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/fees-accounts"
NOW = datetime(2026, 10, 22, 9, 30, tzinfo=UTC)
TODAY = NOW.date().isoformat()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with one user per role. A student's person_id is their user id."""

    def __init__(self):
        self.id = new_id()
        self.ids: dict[str, str] = {}
        self.headers: dict[str, dict] = {}
        for name, roles in {
            "staff": ["finance-staff"],
            "manager": ["management"],
            "admin": ["org-admin"],
            "student": ["student"],
            "classmate": ["student"],
            "applicant": ["applicant"],
            "exams": ["examination-staff"],
            "nobody": [],
        }.items():
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


def head(client, org: Org, code: str = "TUITION", category: str = "tuition", name: str | None = None) -> dict:
    r = client.post(
        f"{BASE}/fee-heads", json={"code": code, "name": name or code.title(), "category": category}, headers=org.staff
    )
    assert r.status_code == 201, r.text
    return r.json()


def structure_body(heads: list[dict], **overrides) -> dict:
    body = {
        "name": "BSc 2026-27",
        "academic_year": "2026-27",
        "items": [{"fee_head_id": h["id"], "amount": a} for h, a in zip(heads, ["30000.00", "10000.00"], strict=False)],
        "instalments": [
            {"label": "Term 1", "percent": 60, "due_date": "2026-10-31"},
            {"label": "Term 2", "percent": 40, "due_date": "2027-01-31"},
        ],
    }
    body.update(overrides)
    return body


def published(client, org: Org, heads: list[dict] | None = None, **overrides) -> dict:
    heads = heads or [head(client, org, f"T{new_id()[:6].upper()}")]
    r = client.post(f"{BASE}/fee-structures", json=structure_body(heads, **overrides), headers=org.staff)
    assert r.status_code == 201, r.text
    r = client.post(f"{BASE}/fee-structures/{r.json()['id']}/publish", headers=org.staff)
    assert r.status_code == 200, r.text
    return r.json()


def invoice(
    client, org: Org, person: str = "student", structure: dict | None = None, instalment: int = 1, **extra
) -> dict:
    structure = structure or published(client, org)
    body = {
        "person_id": org.ids.get(person, person),
        "fee_structure_id": structure["id"],
        "instalment": instalment,
        **extra,
    }
    r = client.post(f"{BASE}/invoices", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    return r.json()


def adhoc(client, org: Org, amount: str = "500.00", due: str = "2026-11-15", person: str = "student", **extra) -> dict:
    h = head(client, org, f"A{new_id()[:6].upper()}", "fine")
    body = {
        "person_id": org.ids.get(person, person),
        "lines": [{"fee_head_id": h["id"], "amount": amount, "description": "Lost ID card"}],
        "due_date": due,
        **extra,
    }
    r = client.post(f"{BASE}/invoices", json=body, headers=org.staff)
    assert r.status_code == 201, r.text
    return r.json()


def pay_cash(client, org: Org, invoice_id: str, amount: str, paid_on: str = TODAY) -> dict:
    r = client.post(
        f"{BASE}/invoices/{invoice_id}/payments",
        json={"amount": amount, "mode": "cash", "paid_on": paid_on},
        headers=org.staff,
    )
    assert r.status_code == 201, r.text
    return r.json()


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]
