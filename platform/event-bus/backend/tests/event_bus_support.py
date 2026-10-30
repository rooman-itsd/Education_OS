"""Helpers shared by the event-bus tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent, publish
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_event_bus.application.consumers import Consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_identity.application.service import create_user

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Clock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def raise_event(name: str, organisation_id: str | None, payload: dict | None = None, at: datetime = NOW) -> str:
    """Publish one event the way a module does: in its own transaction, in its own scope."""
    scope = organisation_scope(organisation_id) if organisation_id else platform_scope()
    with scope, SessionLocal() as db:
        ev = publish(db, name, organisation_id, payload or {})
        ev.occurred_at = at
        db.commit()
        return ev.id


def row(event_id: str) -> OutboxEvent:
    with platform_scope(), SessionLocal() as db:
        return db.get(OutboxEvent, event_id)


def names(prefix: str = "") -> list[str]:
    with platform_scope(), SessionLocal() as db:
        return sorted(r.name for r in db.query(OutboxEvent).all() if r.name.startswith(prefix))


def relay(handlers: dict, clock: Clock, **settings) -> Relay:
    """A relay over the given {module: {event name: handler}} registrations."""
    config = EventBusConfig(**settings)
    return Relay(InProcessTransport(Consumers(handlers)), config, clock=clock)


class Org:
    """An organisation id with real identity users: the API resolves the principal from the users table."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        with organisation_scope(self.id), SessionLocal() as db:
            self.admin = self._user(db, ["org-admin"])
            self.member = self._user(db, ["student"])

    def _user(self, db, roles):
        u = create_user(
            db,
            organisation_id=self.id,
            email=f"u-{uuid.uuid4().hex[:8]}@example.com",
            name="U",
            password="Secret123!",
            roles=roles,
        )
        db.commit()
        return u

    def headers(self, user) -> dict:
        return auth(create_token(user_id=user.id, organisation_id=self.id, roles=list(user.roles)))


def super_admin_headers() -> dict:
    with platform_scope(), SessionLocal() as db:
        u = create_user(
            db,
            organisation_id=None,
            email=f"root-{uuid.uuid4().hex[:8]}@platform.example.com",
            name="Root",
            password="Secret123!",
            roles=["super-admin"],
            is_super_admin=True,
        )
        db.commit()
    return auth(create_token(user_id=u.id, organisation_id=None, roles=["super-admin"], super_admin=True))
