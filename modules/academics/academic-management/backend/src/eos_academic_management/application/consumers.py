"""What academic-management consumes (event-bus entry point `eos.event_consumers`): the three course-registration events
of enrolment-registration, applied by `roster.handle_event` to the roster read model (FR-14). enrolment-registration's
contracts/events.yaml lists this module as a consumer of each of them, and its payloads are the ones roster.py reads.

The relay calls a handler with its own session, already in the event's organisation, and commits afterwards
(platform/event-bus/README.md). `roster.handle_event` takes the envelope as a dict and commits itself, so each handler
only builds that dict from the delivered `Event`. Delivery is at-least-once and unordered; `handle_event` records each
envelope id (`academic_management_processed_event`), so a repeated delivery changes nothing, and it carries the
ordering rules (a withdrawal is never undone by a late confirmation). Its outcome (applied, duplicate, ignored, stale or
rejected:<reason>) is returned for the relay's log; a rejection (a full or closed section, an unknown section) is
recorded and not retried, because redelivering the same event would be refused the same way."""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import roster


def _envelope(event) -> dict:
    return {
        "id": event.id,
        "name": event.name,
        "version": getattr(event, "version", 1) or 1,
        "organisation_id": event.organisation_id,
        "actor": getattr(event, "actor", None),
        "occurred_at": event.occurred_at,
        "payload": event.payload,
    }


def on_registration_confirmed(db: Session, event) -> str:
    return roster.handle_event(db, _envelope(event))


def on_registration_withdrawn(db: Session, event) -> str:
    return roster.handle_event(db, _envelope(event))


def on_section_changed(db: Session, event) -> str:
    return roster.handle_event(db, _envelope(event))


# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    roster.CONFIRMED: on_registration_confirmed,
    roster.WITHDRAWN: on_registration_withdrawn,
    roster.SECTION_CHANGED: on_section_changed,
}
