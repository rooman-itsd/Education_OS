"""Helpers shared by the notification tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import create_user
from eos_notification.infrastructure.transport import OutboundMessage, SendResult
from sqlalchemy import select

PREFIX = "/api/v1/notification"
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def later(seconds: float, base: datetime = NOW) -> datetime:
    return base + timedelta(seconds=seconds)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation id with real identity users (the module resolves addresses from identity)."""

    def __init__(self, db):
        self.id = str(uuid.uuid4())
        # The inserts must run as this organisation: on PostgreSQL the tenant_isolation policy's WITH CHECK
        # refuses a row written with no tenant set. On SQLite this changes nothing.
        with organisation_scope(self.id):
            self.admin = self.user(db, ["org-admin"], "admin")
            self.member = self.user(db, ["member"], "member")
            self.sender = self.user(db, ["test-sender"], "sender")

    @classmethod
    def create(cls, db):
        return cls(db)

    def user(self, db, roles: list[str], label: str = "user"):
        u = create_user(
            db,
            organisation_id=self.id,
            email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
            name=label,
            password="Secret123!",
            roles=roles,
        )
        db.commit()
        return u

    def token(self, user) -> str:
        return create_token(user_id=user.id, organisation_id=self.id, roles=list(user.roles))

    def headers(self, user) -> dict:
        return auth(self.token(user))


def verify_request(**overrides) -> dict:
    """A secret-bearing request: a token plus the non-secret id of the issuance that produced it."""
    request = {
        "template": "tenancy.organisation.verify",
        "recipient": {"address": "admin@college.example.com"},
        "variables": {"organisation_name": "College", "token": "s3cr3t-token-value", "token_id": str(uuid.uuid4())},
        "client_token": f"verify-{uuid.uuid4()}",
    }
    request.update(overrides)
    return request


def reminder_request(user_id: str | None = None, **overrides) -> dict:
    request = {
        "template": "billing.trial.reminder",
        "recipient": {"user_id": user_id} if user_id else {"address": "person@college.example.com"},
        "variables": {"organisation_name": "College", "trial_ends_on": "2026-10-20", "days_left": 3},
        "client_token": f"reminder-{uuid.uuid4()}",
    }
    request.update(overrides)
    return request


class ScriptedTransport:
    """Answers each send with the next scripted result (the last one repeats) and records what it was given."""

    def __init__(self, *results: SendResult):
        self.results = list(results) or [SendResult(True, "scripted-1")]
        self.sent: list[OutboundMessage] = []

    def send(self, message: OutboundMessage) -> SendResult:
        self.sent.append(message)
        result = self.results[min(len(self.sent), len(self.results)) - 1]
        if isinstance(result, Exception):
            raise result
        return result


def outbox_names(db, organisation_id: str, prefix: str = "notification.") -> list[str]:
    with platform_scope():
        rows = db.scalars(
            select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id).order_by(OutboxEvent.occurred_at)
        ).all()
    return [e.name for e in rows if e.name.startswith(prefix)]


def outbox_events(db, organisation_id: str, name: str) -> list[OutboxEvent]:
    with platform_scope():
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)).all()
    return [e for e in rows if e.name == name]
