"""Helpers shared by the e-office tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/e-office"
NOW = datetime(2026, 10, 31, 6, 0, tzinfo=UTC)  # 11:30 on 31 October in Asia/Kolkata
TODAY = "2026-10-31"
_codes = itertools.count(1)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Clock:
    """The service's clock, moved by tests."""

    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now = self.now + timedelta(**delta)


class Org:
    """An organisation with one user per role."""

    ROLES = {
        "hr": ["hr-staff"],
        "hr2": ["hr-staff"],
        "finance": ["finance-staff"],
        "dept": ["department-admin"],
        "manager": ["management"],
        "admin": ["org-admin"],
        "faculty": ["faculty"],
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


def category(client, org: Org, code: str | None = None, **fields) -> dict:
    body = {"code": code or f"CAT-{next(_codes)}", "name": "Administration", **fields}
    r = client.post(f"{BASE}/categories", json=body, headers=org.admin)
    assert r.status_code == 201, r.text
    return r.json()


def open_file(client, org: Org, who: str = "hr", cat: dict | None = None, **fields) -> dict:
    cat = cat or category(client, org)
    body = {"subject": "Revision of leave rules", "category_id": cat["id"], **fields}
    r = client.post(f"{BASE}/files", json=body, headers=org.headers[who])
    assert r.status_code == 201, r.text
    return r.json()


def forward(client, org: Org, f: dict, who: str, to: str, **fields):
    body = {"to_user_id": org.ids[to], **fields}
    return client.post(f"{BASE}/files/{f['id']}/forward", json=body, headers=org.headers[who])


def note(client, org: Org, f: dict, who: str, text: str = "Put up for consideration.", **fields):
    return client.post(f"{BASE}/files/{f['id']}/notes", json={"text": text, **fields}, headers=org.headers[who])


def attach(client, org: Org, f: dict, who: str, **fields):
    body = {"document_id": f"doc-{new_id()[:8]}", "title": "Draft letter", **fields}
    return client.post(f"{BASE}/files/{f['id']}/attachments", json=body, headers=org.headers[who])


def decide(client, org: Org, f: dict, who: str, decision: str = "approved", **fields):
    body = {"decision": decision, "remark": "Approved as proposed.", **fields}
    return client.post(f"{BASE}/files/{f['id']}/decision", json=body, headers=org.headers[who])


def receipt(client, org: Org, to: str = "hr2", **fields) -> dict:
    body = {
        "received_on": TODAY,
        "sender": "Directorate of Education",
        "subject": "Circular on staff training",
        "mode": "post",
        "document_id": "scan-1",
        "send_to_user_id": org.ids[to],
        **fields,
    }
    r = client.post(f"{BASE}/receipts", json=body, headers=org.hr)
    assert r.status_code == 201, r.text
    return r.json()


def approved_file(client, org: Org) -> tuple[dict, dict]:
    """A file opened by hr, with a letter attached, approved by the department admin and returned to hr."""
    f = open_file(client, org)
    letter = attach(client, org, f, "hr", kind="draft").json()
    assert forward(client, org, f, "hr", "dept", action_required="for approval").status_code == 200
    r = decide(client, org, f, "dept", forward_to_user_id=org.ids["hr"])
    assert r.status_code == 200, r.text
    return r.json(), letter


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]
