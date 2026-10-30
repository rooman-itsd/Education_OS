"""The relay: the missing half of the transactional outbox (docs/outbox-relay.md).

One pass (`run_once`):
1. claim the oldest deliverable rows: not published, under the attempt limit, past their backoff; on Postgres
   FOR UPDATE SKIP LOCKED, so several relays never deliver the same row at once;
2. hand them to the transport;
3. mark delivered rows published; for a failed one count the attempt, record a short reason and back off
   exponentially (1 s, 2 s, 4 s ... capped), or dead-letter it at the limit and raise
   event-bus.event.dead-lettered;
4. raise event-bus.relay.stalled once when the oldest pending event is older than the threshold.

The claim runs in platform scope: the relay reads every organisation's events by design. Each consumer then runs
in its event's own organisation (transport.scope_of)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from eos_core.db import SessionLocal, utcnow
from eos_core.events import OutboxEvent, publish
from eos_core.tenant import platform_scope
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..domain.models import Event
from ..infrastructure.config import EventBusConfig
from .transport import Transport

log = logging.getLogger("eos.event_bus")

DEAD_LETTERED = "event-bus.event.dead-lettered"
STALLED = "event-bus.relay.stalled"
OWN_PREFIX = "event-bus."


@dataclass(frozen=True)
class Pass:
    claimed: int = 0
    delivered: int = 0
    failed: int = 0
    dead_lettered: int = 0


def backoff(attempts: int, cap_s: int) -> timedelta:
    """1 s after the first failure, doubling, never more than cap_s."""
    return timedelta(seconds=min(2 ** max(attempts - 1, 0), cap_s))


def pending_filter(max_attempts: int):
    return (OutboxEvent.published.is_(False), OutboxEvent.attempts < max_attempts)


class Relay:
    def __init__(
        self,
        transport: Transport,
        config: EventBusConfig,
        session_factory: Callable[[], Session] = SessionLocal,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.transport = transport
        self.config = config
        self._sessions = session_factory
        self._now = clock
        self._stalled = False  # process-local: one stalled event per stall, not one per pass

    def run_once(self) -> Pass:
        now = self._now()
        with self._sessions() as db:
            # The claim's transaction begins in platform scope, so it sees and locks every organisation's rows;
            # Postgres keeps those settings for the whole transaction. Delivery then runs OUTSIDE platform scope:
            # each consumer's own session begins in its event's organisation with the bypass off.
            with platform_scope():
                rows = self._claim(db, now)
            delivery = self.transport.deliver([Event.of(r) for r in rows]) if rows else None
            with platform_scope():
                result = self._record(db, rows, delivery.accepted, delivery.failed, now) if delivery else Pass()
                self._check_stall(db, now)
                db.commit()
        return result

    def _claim(self, db: Session, now: datetime) -> list[OutboxEvent]:
        q = (
            select(OutboxEvent)
            .where(
                *pending_filter(self.config.max_attempts),
                or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
            )
            .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
            .limit(self.config.batch_size)
        )
        if db.get_bind().dialect.name == "postgresql":
            q = q.with_for_update(skip_locked=True)
        return list(db.scalars(q))

    def _record(
        self, db: Session, rows: list[OutboxEvent], accepted: list[str], failed: dict[str, str], now: datetime
    ) -> Pass:
        delivered = dead = 0
        ok = set(accepted)
        for row in rows:
            if row.id in ok:
                row.published, row.published_at = True, now
                row.last_error, row.next_attempt_at = None, None
                delivered += 1
                continue
            row.attempts = (row.attempts or 0) + 1
            row.last_error = failed.get(row.id, "not accepted by the transport")[:500]
            if row.attempts >= self.config.max_attempts:
                row.next_attempt_at = None
                dead += 1
                log.error("event %s (%s) dead-lettered after %s attempts", row.id, row.name, row.attempts)
                # Never for the bus's own events: a dead-lettered notice that cannot be delivered must not raise
                # another one about itself.
                if not row.name.startswith(OWN_PREFIX):
                    self._notice(
                        db,
                        DEAD_LETTERED,
                        row.organisation_id,
                        {
                            "event_id": row.id,
                            "event_name": row.name,
                            "attempts": row.attempts,
                            "last_error": row.last_error,
                        },
                        now,
                    )
            else:
                row.next_attempt_at = now + backoff(row.attempts, self.config.retry_cap_s)
        return Pass(claimed=len(rows), delivered=delivered, failed=len(rows) - delivered, dead_lettered=dead)

    def _check_stall(self, db: Session, now: datetime) -> None:
        oldest = db.scalar(select(func.min(OutboxEvent.occurred_at)).where(*pending_filter(self.config.max_attempts)))
        if oldest is not None and oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=now.tzinfo)  # SQLite returns naive datetimes; every stored time is UTC
        stalled = oldest is not None and (now - oldest).total_seconds() > self.config.stall_threshold_s
        if stalled and not self._stalled:
            backlog = db.scalar(
                select(func.count()).select_from(OutboxEvent).where(*pending_filter(self.config.max_attempts))
            )
            log.error("relay stalled: %s pending, oldest from %s", backlog, oldest.isoformat())
            self._notice(
                db,
                STALLED,
                None,
                {"backlog": backlog, "oldest_unpublished_at": oldest.isoformat(), "transport": self.transport.name},
                now,
            )
        self._stalled = stalled

    @staticmethod
    def _notice(db: Session, name: str, organisation_id: str | None, payload: dict, now: datetime) -> None:
        """The bus's own events, timed by the relay's clock like everything else it records."""
        publish(db, name, organisation_id, payload).occurred_at = now

    def prune(self) -> int:
        """Delete delivered events older than the retention window. Pending and dead-lettered rows are kept."""
        cutoff = self._now() - timedelta(days=self.config.retention_days)
        with platform_scope(), self._sessions() as db:
            removed = db.execute(
                delete(OutboxEvent).where(OutboxEvent.published.is_(True), OutboxEvent.published_at < cutoff)
            ).rowcount
            db.commit()
        return removed or 0

    def run_forever(self, stop: threading.Event, prune_every_s: int = 3600) -> None:
        """Pass after pass; sleep the poll interval only when there was nothing to claim."""
        next_prune = 0.0
        while not stop.is_set():
            try:
                result = self.run_once()
                if time.monotonic() >= next_prune:
                    self.prune()
                    next_prune = time.monotonic() + prune_every_s
            except Exception:  # noqa: BLE001 - a database blip must not end the relay; the next pass retries
                log.exception("relay pass failed")
                result = Pass()
            if result.claimed == 0:
                stop.wait(self.config.poll_interval_ms / 1000)
