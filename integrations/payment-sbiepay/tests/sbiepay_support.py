"""Helpers shared by the payment-sbiepay tests (kept out of conftest.py so test files can import them)."""

import re
import uuid

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

NOTIFY_SECRET = "test-notify-secret"
PREFIX = "/api/v1/payment-sbiepay"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with an org admin, a finance staff member and a student, each with a platform token."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.admin_id, self.staff_id, self.student_id = (str(uuid.uuid4()) for _ in range(3))
        self.admin = auth(create_token(user_id=self.admin_id, organisation_id=self.id, roles=["org-admin"]))
        self.staff = auth(create_token(user_id=self.staff_id, organisation_id=self.id, roles=["finance-staff"]))
        self.student = auth(create_token(user_id=self.student_id, organisation_id=self.id, roles=["student"]))

    def token(self, who: str) -> str:
        return getattr(self, who)["Authorization"].split(" ", 1)[1]


def payment_body(**overrides) -> dict:
    body = {
        "purpose": "subscription",
        "source_module": "billing",
        "source_reference": str(uuid.uuid4()),
        "amount": "1500.00",
        "currency": "INR",
        "return_url": "https://college.example.com/billing/return",
        "notify_url": "https://api.example.com/api/v1/billing/webhooks/payment",
    }
    body.update(overrides)
    return body


def start(client, headers: dict, **overrides) -> dict:
    r = client.post(f"{PREFIX}/payments", json=payment_body(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def browser_pays(client, session: dict, outcome: str = "success"):
    """Open payment_url, then post the gateway's answer to the callback as the payer's browser would."""
    page = client.get(session["payment_url"])
    assert page.status_code == 200, page.text
    action = re.search(r'action="([^"]+)"', page.text).group(1)
    fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', page.text))
    fields["mock_outcome"] = outcome
    return client.post(action, data=fields, follow_redirects=False)


def outbox(name: str, organisation_id: str) -> list[OutboxEvent]:
    db = SessionLocal()
    try:
        with platform_scope():
            return list(
                db.scalars(
                    select(OutboxEvent)
                    .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
                    .order_by(OutboxEvent.occurred_at)
                )
            )
    finally:
        db.close()
