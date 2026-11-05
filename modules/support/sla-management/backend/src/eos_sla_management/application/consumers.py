"""What sla-management consumes (event-bus entry point `eos.event_consumers`, module.yaml consumes_events): helpdesk's
ticket events, which drive the clocks (PRD main flows 3 to 12). The relay calls each handler with its own session, in
the event's organisation, and commits afterwards (platform/event-bus).

Each handler reads only fields of modules/support/helpdesk/contracts/events.yaml:
- created:        ticket_id, number, category_id, queue_id, priority, created_at -> start both clocks
- assigned:       ticket_id, queue_id, assignee_id (envelope occurred_at)      -> cached queue and assignee
- responded:      ticket_id, responded_at                                       -> stop the response clock
- status-changed: ticket_id, to_status, hold_reason, changed_at                 -> pause or resume
- reclassified:   ticket_id, category_id, priority (envelope occurred_at)       -> recalculate
- resolved:       ticket_id, resolved_at                                        -> stop both clocks
- reopened:       ticket_id, assignee_id, reopened_at                           -> resume the resolution clock
- closed:         ticket_id, closed_at                                          -> final; stop anything still open
- cancelled:      ticket_id, cancelled_at                                       -> final; cancel open clocks

Rules:
- The organisation is the envelope's organisation_id, never a payload field, and the session must be scoped to it
  (the relay does this); an event without one is not ours and is ignored.
- Each event is applied once, by envelope id: the id is recorded in processed_event with INSERT ... ON CONFLICT DO
  NOTHING in the handler's transaction, so a duplicate delivery, also a concurrent one, changes nothing.
- One ticket's events are applied one at a time: each locks the ticket's ticket_ref row first.
- A malformed event (no or a non-string id, a missing field, an id that is not a UUID, an unknown priority, a time
  that is not an ISO date-time between 2000 and 2099, an unsupported envelope version) is logged without its content
  and ignored, never raised: retrying cannot fix it, and raising would make the relay retry it until it is
  dead-lettered. A naive time is read as UTC.
- An event for a ticket sla-management does not track (unknown, or created when no policy matched) changes nothing,
  except assigned, which is kept for a ticket whose created event has not arrived yet.
- Events are applied in arrival order (out-of-order delivery is PRD open question 1); a time earlier than the clock's
  last change counts as that change's time (engine.py).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..domain import business_time as bt
from ..domain import clocks as rules
from ..domain.policies import PRIORITIES, choose
from ..infrastructure import repository as repo
from ..infrastructure.models import Clock, TicketRef
from . import engine
from .engine import Run

log = logging.getLogger("eos.sla_management")

SOURCE = "helpdesk"
CREATED = f"{SOURCE}.ticket.created"
ASSIGNED = f"{SOURCE}.ticket.assigned"
RESPONDED = f"{SOURCE}.ticket.responded"
STATUS_CHANGED = f"{SOURCE}.ticket.status-changed"
RECLASSIFIED = f"{SOURCE}.ticket.reclassified"
RESOLVED = f"{SOURCE}.ticket.resolved"
REOPENED = f"{SOURCE}.ticket.reopened"
CLOSED = f"{SOURCE}.ticket.closed"
CANCELLED = f"{SOURCE}.ticket.cancelled"

ON_HOLD = "on_hold"
SUPPORTED_VERSION = 1
APPLIED, DUPLICATE, IGNORED = "applied", "duplicate", "ignored"

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MISSING = object()


class MalformedEventError(ValueError):
    """A payload or envelope value this module cannot use. Caught in _receive: the event is ignored."""


# ---------------------------------------------------------------- reading payload values


def _value(payload: dict, name: str):
    value = payload.get(name, MISSING)
    if value is MISSING:
        raise MalformedEventError(f"{name} is missing")
    return value


def _text(payload: dict, name: str, max_length: int, *, nullable: bool = False) -> str | None:
    value = _value(payload, name)
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not 0 < len(value) <= max_length:
        raise MalformedEventError(f"{name} must be a string of 1 to {max_length} characters")
    return value


def _id(payload: dict, name: str, *, nullable: bool = False) -> str | None:
    value = _text(payload, name, 36, nullable=nullable)
    if value is None:
        return None
    if not UUID.match(value):
        raise MalformedEventError(f"{name} must be a UUID")
    return value.lower()


def _priority(payload: dict) -> str:
    value = _text(payload, "priority", 10)
    if value not in PRIORITIES:
        raise MalformedEventError("priority is not a helpdesk priority")
    return value


def _instant(value, name: str) -> datetime:
    if isinstance(value, str) and len(value) <= 40:
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise MalformedEventError(f"{name} must be an ISO date-time") from None
    if not isinstance(value, datetime):
        raise MalformedEventError(f"{name} must be an ISO date-time")
    try:
        # astimezone overflows for well-formed times at the ends of the calendar (9999-12-31T23:59:59-23:59), before
        # the range check below can refuse them; that is a malformed event, not one for the relay to retry.
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    except (OverflowError, ValueError):
        raise MalformedEventError(f"{name} must be between 2000 and 2099") from None
    if not bt.in_range(value):
        raise MalformedEventError(f"{name} must be between 2000 and 2099")
    return value


def _time(payload: dict, name: str) -> datetime:
    return _instant(_value(payload, name), name)


def _occurred(event) -> datetime:
    return _instant(getattr(event, "occurred_at", None), "occurred_at")


# ---------------------------------------------------------------- the common path


def _receive(db: Session, event, parse: Callable[[dict, object], dict], apply: Callable[[Run, dict], str]) -> str:
    """Check the envelope, read the payload, record the event id, apply once."""
    name, event_id = getattr(event, "name", None), getattr(event, "id", None)
    organisation_id = getattr(event, "organisation_id", None)
    if not isinstance(organisation_id, str) or not 0 < len(organisation_id) <= 36:
        log.warning("sla-management: %s has no organisation; ignored", name)
        return IGNORED
    if not isinstance(event_id, str) or not 0 < len(event_id) <= 36 or not isinstance(name, str):
        log.warning("sla-management: an event without a usable id or name; ignored")
        return IGNORED
    if resolve_organisation(db) != organisation_id:
        # The relay runs the handler in the event's organisation. Anything else would write one organisation's
        # event under another's row-level security: refuse rather than guess. This is not the event's fault.
        raise RuntimeError("the session is not scoped to the event's organisation")
    version = getattr(event, "version", None) or 1
    if version != SUPPORTED_VERSION:
        log.warning("sla-management: %s %s has envelope version %r; ignored", name, event_id, version)
        return IGNORED
    payload = getattr(event, "payload", None)
    try:
        if not isinstance(payload, dict):
            raise MalformedEventError("payload must be an object")
        values = parse(payload, event)
    except MalformedEventError as err:
        log.warning("sla-management: %s %s is malformed (%s); ignored", name, event_id, err)
        return IGNORED
    if not repo.mark_processed(db, organisation_id, event_id, name):
        return DUPLICATE
    return apply(Run(db, organisation_id, f"{name} {event_id}"), values)


def _tracked(run: Run, ticket_id: str) -> tuple[TicketRef, list[Clock]] | None:
    """The locked ticket and its clocks, when the ticket is tracked."""
    ref = repo.ticket_ref(run.db, run.organisation_id, ticket_id, create=False)
    if ref is None or not ref.created:
        return None
    clocks = repo.clocks_of_ticket(run.db, ticket_id)
    return (ref, clocks) if clocks else None


def _catch_up(run: Run, clocks: list[Clock], at: datetime) -> None:
    for clock in clocks:
        engine.catch_up(run, clock, at)


# ---------------------------------------------------------------- created and assigned


def _parse_created(p: dict, event) -> dict:
    return {
        "ticket_id": _id(p, "ticket_id"),
        "number": _text(p, "number", 40),
        "category_id": _id(p, "category_id", nullable=True),
        "queue_id": _id(p, "queue_id", nullable=True),
        "priority": _priority(p),
        "at": _time(p, "created_at"),
    }


def _created(run: Run, v: dict) -> str:
    """Both clocks start at created_at under the most specific active policy; none matching leaves the ticket
    untracked and publishes nothing (PRD main flow 3, open question 5)."""
    ref = repo.ticket_ref(run.db, run.organisation_id, v["ticket_id"], create=True)
    if ref.created:
        return IGNORED  # a second creation of the same ticket under another event id
    ref.created, ref.number, ref.priority, ref.category_id = True, v["number"], v["priority"], v["category_id"]
    ref.queue_id = ref.queue_id or v["queue_id"]  # an assignment that arrived first is newer
    policy = choose(repo.policies(run.db, priority=v["priority"], active=True), v["priority"], v["category_id"])
    if policy is None:
        return APPLIED
    for kind in rules.KINDS:
        engine.start(run, ref, kind, policy, v["at"])
    return APPLIED


def _parse_assigned(p: dict, event) -> dict:
    return {
        "ticket_id": _id(p, "ticket_id"),
        "queue_id": _id(p, "queue_id", nullable=True),
        "assignee_id": _id(p, "assignee_id", nullable=True),
        "at": _occurred(event),
    }


def _assigned(run: Run, v: dict) -> str:
    """The cached queue and assignee, for the mine scope and escalation recipients (PRD main flow 12). What fell due
    before the assignment is recorded first, so it names the previous assignee."""
    ref = repo.ticket_ref(run.db, run.organisation_id, v["ticket_id"], create=True)
    clocks = repo.clocks_of_ticket(run.db, v["ticket_id"])
    _catch_up(run, clocks, v["at"])
    ref.assignee_id = v["assignee_id"]
    if v["queue_id"] is not None:
        ref.queue_id = v["queue_id"]
    for clock in clocks:
        clock.assignee_id, clock.queue_id = ref.assignee_id, ref.queue_id
    return APPLIED


# ---------------------------------------------------------------- responded, status, reclassified


def _ticket_time(field: str) -> Callable[[dict, object], dict]:
    def parse(p: dict, event) -> dict:
        return {"ticket_id": _id(p, "ticket_id"), "at": _time(p, field)}

    return parse


def _responded(run: Run, v: dict) -> str:
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    _, clocks = found
    _catch_up(run, clocks, v["at"])
    for clock in clocks:
        if clock.kind == rules.RESPONSE:
            engine.stop(run, clock, v["at"])
    return APPLIED


def _parse_status(p: dict, event) -> dict:
    return {
        "ticket_id": _id(p, "ticket_id"),
        "to_status": _text(p, "to_status", 20),
        "hold_reason": _text(p, "hold_reason", 40, nullable=True),
        "at": _time(p, "changed_at"),
    }


def _status_changed(run: Run, v: dict) -> str:
    """On hold for a reason the clock's policy pauses on pauses every running clock; any other status, or a hold
    reason that does not pause, resumes paused clocks (PRD main flow 5)."""
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    _, clocks = found
    _catch_up(run, clocks, v["at"])
    for clock in clocks:
        pauses = v["to_status"] == ON_HOLD and v["hold_reason"] in (clock.pause_on_hold_reasons or [])
        if pauses:
            engine.pause(run, clock, v["at"])
        else:
            engine.resume(run, clock, v["at"])
    return APPLIED


def _parse_reclassified(p: dict, event) -> dict:
    return {
        "ticket_id": _id(p, "ticket_id"),
        "category_id": _id(p, "category_id", nullable=True),
        "priority": _priority(p),
        "at": _occurred(event),
    }


def _reclassified(run: Run, v: dict) -> str:
    """Running and paused clocks move to the policy for the new category and priority; with none, they keep their
    targets (PRD main flow 6). A ticket untracked at creation stays untracked."""
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    ref, clocks = found
    _catch_up(run, clocks, v["at"])
    ref.category_id, ref.priority = v["category_id"], v["priority"]
    for clock in clocks:
        clock.category_id, clock.priority = ref.category_id, ref.priority
    policy = choose(repo.policies(run.db, priority=v["priority"], active=True), v["priority"], v["category_id"])
    if policy is not None:
        for clock in clocks:
            engine.recalculate(run, clock, policy, v["at"])
    return APPLIED


# ---------------------------------------------------------------- resolved, reopened, closed, cancelled


def _resolved(run: Run, v: dict) -> str:
    """Stops the resolution clock, and the response clock too when there was no public reply first (PRD flow 9)."""
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    _, clocks = found
    _catch_up(run, clocks, v["at"])
    for clock in clocks:
        engine.stop(run, clock, v["at"])
    return APPLIED


def _parse_reopened(p: dict, event) -> dict:
    return {
        "ticket_id": _id(p, "ticket_id"),
        "assignee_id": _id(p, "assignee_id", nullable=True),
        "at": _time(p, "reopened_at"),
    }


def _reopened(run: Run, v: dict) -> str:
    """The resolution clock resumes from where it stopped (PRD flow 10); a closed or cancelled ticket stays final."""
    found = _tracked(run, v["ticket_id"])
    if found is None or found[0].final:
        return IGNORED
    ref, clocks = found
    ref.assignee_id = v["assignee_id"]
    for clock in clocks:
        clock.assignee_id = ref.assignee_id
        if clock.kind == rules.RESOLUTION:
            engine.resume(run, clock, v["at"], move="reopen")
    return APPLIED


def _closed(run: Run, v: dict) -> str:
    """Final: no reopen is expected. A clock still open (closed without resolving first) is stopped."""
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    ref, clocks = found
    ref.final = True
    _catch_up(run, clocks, v["at"])
    for clock in clocks:
        engine.stop(run, clock, v["at"])
    return APPLIED


def _cancelled(run: Run, v: dict) -> str:
    """Final: every running or paused clock is cancelled; stopped clocks keep their outcome (PRD flow 11)."""
    found = _tracked(run, v["ticket_id"])
    if found is None:
        return IGNORED
    ref, clocks = found
    ref.final = True
    _catch_up(run, clocks, v["at"])
    for clock in clocks:
        engine.cancel(run, clock, v["at"])
    return APPLIED


def _handler(parse, apply):
    def handle(db: Session, event) -> str:
        return _receive(db, event, parse, apply)

    return handle


on_created = _handler(_parse_created, _created)
on_assigned = _handler(_parse_assigned, _assigned)
on_responded = _handler(_ticket_time("responded_at"), _responded)
on_status_changed = _handler(_parse_status, _status_changed)
on_reclassified = _handler(_parse_reclassified, _reclassified)
on_resolved = _handler(_ticket_time("resolved_at"), _resolved)
on_reopened = _handler(_parse_reopened, _reopened)
on_closed = _handler(_ticket_time("closed_at"), _closed)
on_cancelled = _handler(_ticket_time("cancelled_at"), _cancelled)

# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    CREATED: on_created,
    ASSIGNED: on_assigned,
    RESPONDED: on_responded,
    STATUS_CHANGED: on_status_changed,
    RECLASSIFIED: on_reclassified,
    RESOLVED: on_resolved,
    REOPENED: on_reopened,
    CLOSED: on_closed,
    CANCELLED: on_cancelled,
}
