"""Where the relay hands events. The relay depends on this port only, so a broker transport (redis-streams,
rabbitmq, kafka; after the broker ADR) is one more class and touches no module (docs/outbox-relay.md).

`inprocess` delivers to the consumers registered in this process. Each handler runs in its own session and
transaction, in the event's organisation, so row-level security applies to its writes exactly as it does to an
API request.

Delivery is tracked per consuming module (EventDelivery, the consumer group per module of #83):
- a handler's `delivered` mark is written in the handler's own transaction, so it exists exactly when the
  handler's writes committed;
- a module already delivered is skipped, so a retry or a replay re-runs only the modules that failed;
- a failing module does not stop the others: every module gets its turn on every attempt;
- the event is accepted when every module is delivered. Otherwise it fails, and the relay retries it with backoff
  and finally dead-letters it, naming the modules that failed.
Delivery to a module is still at-least-once (a crash between its commit and the relay's own commit re-runs
nothing already marked, but a handler that commits elsewhere first may run again), so handlers stay idempotent on
event.id."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from eos_core.db import SessionLocal, utcnow
from eos_core.tenant import is_bypass, organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import DELIVERED, FAILED, Event, EventDelivery
from .consumers import Consumers

log = logging.getLogger("eos.event_bus")


@dataclass
class Delivery:
    accepted: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # event id -> short reason, never the exception text
    failed_modules: dict[str, list[str]] = field(default_factory=dict)  # event id -> modules not yet delivered


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
            failures = self._deliver_one(event)
            if not failures:
                result.accepted.append(event.id)
            else:
                result.failed[event.id] = "; ".join(f"{module}: {kind}" for module, kind in failures)
                result.failed_modules[event.id] = [module for module, _ in failures]
        return result

    def _deliver_one(self, event: Event) -> list[tuple[str, str]]:
        """Run every module not yet delivered; return (module, exception type) for each that failed."""
        consumers = self._consumers.for_event(event.name)
        if not consumers:
            return []
        done = self._delivered(event)
        failures: list[tuple[str, str]] = []
        for module, handler in consumers:
            if module in done:
                continue
            try:
                with scope_of(event), self._sessions() as db:
                    try:
                        handler(db, event)
                        _mark(db, event, module, DELIVERED, None)  # in the handler's transaction
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
            except Exception as e:  # noqa: BLE001 - any handler failure is a retry, never a relay crash
                # The type only: an exception message can carry the payload's personal data.
                kind = type(e).__name__
                log.warning("event %s (%s) not handled by %s: %s", event.id, event.name, module, kind)
                self._record_failure(event, module, kind)
                failures.append((module, kind))
        return failures

    def _delivered(self, event: Event) -> set[str]:
        with scope_of(event), self._sessions() as db:
            return set(
                db.scalars(
                    select(EventDelivery.module).where(
                        EventDelivery.event_id == event.id, EventDelivery.status == DELIVERED
                    )
                )
            )

    def _record_failure(self, event: Event, module: str, kind: str) -> None:
        """Counted in a session of its own: the handler's was rolled back. Never lets a bookkeeping error mask
        the failure itself; the event is retried either way."""
        try:
            with scope_of(event), self._sessions() as db:
                _mark(db, event, module, FAILED, f"{module}: {kind}")
                db.commit()
        except Exception:  # noqa: BLE001
            log.exception("could not record the failed delivery of %s to %s", event.id, module)


def _mark(db: Session, event: Event, module: str, status: str, error: str | None) -> None:
    row = db.scalar(select(EventDelivery).where(EventDelivery.event_id == event.id, EventDelivery.module == module))
    if row is None:
        row = EventDelivery(event_id=event.id, module=module, organisation_id=event.organisation_id, attempts=0)
        db.add(row)
    now = utcnow()
    row.status, row.attempts, row.updated_at = status, (row.attempts or 0) + 1, now
    row.last_error = error[:500] if error else None
    if status == DELIVERED:
        row.delivered_at = now
    db.flush()
