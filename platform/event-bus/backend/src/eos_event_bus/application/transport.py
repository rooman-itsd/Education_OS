"""Where the relay hands events. The relay depends on this port only, so a broker transport (redis-streams,
rabbitmq, kafka; after the broker ADR) is one more class and touches no module (docs/outbox-relay.md).

`inprocess` delivers to the consumers registered in this process. Each handler runs in its own session and
transaction, in the event's organisation, so row-level security applies to its writes exactly as it does to an
API request. An event is accepted only when every handler for it committed; if one fails the whole event is
retried, so a handler that already succeeded runs again: that is the at-least-once contract, and why every
handler must be idempotent on event.id."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from eos_core.db import SessionLocal
from eos_core.tenant import is_bypass, organisation_scope, platform_scope
from sqlalchemy.orm import Session

from ..domain.models import Event
from .consumers import Consumers

log = logging.getLogger("eos.event_bus")


@dataclass
class Delivery:
    accepted: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # event id -> short reason, never the exception text


class Transport(Protocol):
    name: str

    def deliver(self, events: list[Event]) -> Delivery: ...


@contextmanager
def scope_of(event: Event) -> Iterator[None]:
    """The event's own organisation; a platform-level event (no organisation) runs in platform scope."""
    if event.organisation_id:
        # organisation_scope sets the tenant but leaves an outer platform scope's bypass on, which would let the
        # consumer read and write every organisation. Refuse rather than run it that way.
        if is_bypass():
            raise RuntimeError("an organisation's event must not be delivered from inside platform scope")
        with organisation_scope(event.organisation_id):
            yield
    else:
        with platform_scope():
            yield


class InProcessTransport:
    name = "inprocess"

    def __init__(self, consumers: Consumers, session_factory: Callable[[], Session] = SessionLocal):
        self._consumers = consumers
        self._sessions = session_factory

    def deliver(self, events: list[Event]) -> Delivery:
        result = Delivery()
        for event in events:
            reason = self._deliver_one(event)
            if reason is None:
                result.accepted.append(event.id)
            else:
                result.failed[event.id] = reason
        return result

    def _deliver_one(self, event: Event) -> str | None:
        for module, handler in self._consumers.for_event(event.name):
            try:
                with scope_of(event), self._sessions() as db:
                    try:
                        handler(db, event)
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
            except Exception as e:  # noqa: BLE001 - any handler failure is a retry, never a relay crash
                # The type only: an exception message can carry the payload's personal data.
                reason = f"{module}: {type(e).__name__}"
                log.warning("event %s (%s) not handled by %s", event.id, event.name, reason)
                return reason
        return None
