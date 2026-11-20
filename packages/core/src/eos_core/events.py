"""Transactional outbox. Modules publish here in the same transaction as their state change;
a relay (platform/event-bus) moves rows to the broker. Every event carries organisation_id.

The table's DDL belongs to platform/event-bus's Alembic chain; this model must match its head column for column
(platform/event-bus/backend/tests/test_event_bus_migrations.py checks it)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, new_id, utcnow


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    __table_args__ = (Index("ix_outbox_event_published_occurred_at", "published", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # The super admin who was really acting when `actor` is a user being impersonated (security review N3). Null
    # for every other event. Set by publish() from the request's impersonation context, never from a payload.
    impersonated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    # Relay state (platform/event-bus): payload schema version, delivery attempts and the last failure, when it
    # was delivered, and the earliest time a failed event is tried again (exponential backoff).
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Who is really acting while a super admin impersonates an organisation user: the token's `imp` claim. The API host
# sets it for the whole request (apps/backend, eos_backend.actor), before any route or dependency runs, so every
# event the request publishes carries it whichever module publishes and however it names `actor`.
_impersonated_by: ContextVar[str | None] = ContextVar("eos_impersonated_by", default=None)


def current_impersonator() -> str | None:
    """The super admin impersonating the request's user, or None when nobody is impersonating."""
    return _impersonated_by.get()


@contextmanager
def impersonation(super_admin_id: str | None) -> Iterator[None]:
    """Run a block as `super_admin_id` impersonating the token's user (None: nobody is impersonating)."""
    token = _impersonated_by.set(super_admin_id or None)
    try:
        yield
    finally:
        _impersonated_by.reset(token)


def publish(
    session: Session,
    name: str,
    organisation_id: str | None,
    payload: dict,
    actor: str | None = None,
    version: int = 1,
) -> OutboxEvent:
    """`actor` stays the user the request acted as (impersonated or not: their permissions applied); the
    envelope's `impersonated_by` names the super admin behind it, from the request context."""
    ev = OutboxEvent(
        name=name,
        organisation_id=organisation_id,
        payload=payload,
        actor=actor,
        version=version,
        impersonated_by=current_impersonator(),
    )
    session.add(ev)
    return ev
