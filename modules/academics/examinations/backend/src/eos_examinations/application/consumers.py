"""What examinations consumes (event-bus entry point `eos.event_consumers`): academic-management's course-offering
events, kept as the local `offering_ref` read model (PRD sections 9 and 12). The relay calls each handler with its own
session, in the event's organisation, and commits afterwards (platform/event-bus/README.md).

Implemented here:
- `academic-management.offering.created`        -> offering_ref (course and period facts, from the event's snapshot)
- `academic-management.offering.status-changed` -> offering_ref.status

Not consumed, on purpose (docs/reviewer-decisions.md):
- `offering.updated` and `course.updated`: their payloads carry only `changed_fields`, not the new values, and the
  module does not call the owner's API to read them. A change to an offering's course snapshot after its creation is
  therefore not applied to `offering_ref`.
- `course.created` / `course.archived`: `offering.created` already carries the course's code, title, credits and
  department. No deletion event is defined for an offering.
- `term.*`, `faculty-assignment.*`, `curriculum.published` and the enrolment events: later slices.

Delivery is at-least-once and unordered (platform/event-bus/contracts/events.yaml), so:
- Idempotency is keyed on the envelope id, recorded per organisation in `processed_event` before the event is applied;
  a repeated id does nothing. The marker is written in the handler's own transaction, so a failure rolls it back and the
  redelivery applies the event. Two deliveries racing for one id are settled by the table's unique constraint: the loser
  fails and is redelivered as a duplicate.
- A creation never overwrites what a later event already set, and a status change that arrives before its creation
  leaves a partial row that the creation completes (the row is *known* only then).
- A status is replaced only by an event that occurred at or after the one that set it. The envelope `occurred_at` is
  the ordering key the event-bus contract points consumers to; it is compared per row, never across rows or modules,
  and arrival order is never used.
- An event is applied only in its own organisation: the session scope must be the event's organisation, every read
  names the organisation, and rows are written with it. An event with no organisation is not ours."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..domain.errors import DomainRuleError
from ..domain.values import require_id, require_instant, require_number, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import OfferingRef, ProcessedEvent

log = logging.getLogger("eos.examinations")

SOURCE = "academic-management"
OFFERING_CREATED = f"{SOURCE}.offering.created"
OFFERING_STATUS_CHANGED = f"{SOURCE}.offering.status-changed"

SUPPORTED_VERSION = 1
APPLIED, DUPLICATE, IGNORED, STALE = "applied", "duplicate", "ignored", "stale"


class UnsupportedEventVersionError(ValueError):
    """The envelope's version is not one this module understands; the relay records the failure."""


def _field(payload: dict, name: str, check, *args, **kwargs):
    """A required payload field, validated. A malformed event is refused, never half applied: the ValueError reaches
    the relay, which records it (without the text, which can carry data) and retries, then dead-letters."""
    if name not in payload or payload[name] is None:
        raise ValueError(f"{name} is missing")
    try:
        return check(payload[name], name, *args, **kwargs)
    except DomainRuleError as err:
        raise ValueError(f"{name}: {err.message}") from err


def _id(payload: dict, name: str) -> str:
    return _field(payload, name, require_id)


def _text(payload: dict, name: str, max_length: int) -> str:
    return _field(payload, name, require_text, max_length=max_length)


def _credits(payload: dict) -> Decimal:
    return _field(payload, "credits", require_number, minimum=0, maximum=Decimal("9999.99"))


def _instant(event) -> datetime:
    try:
        return require_instant(event.occurred_at, "occurred_at")
    except DomainRuleError as err:
        raise ValueError(f"occurred_at: {err.message}") from err


def _receive(db: Session, event, apply) -> str:
    """The common path of every handler: check the envelope, record the id, apply once."""
    organisation_id = event.organisation_id
    if not organisation_id:
        log.warning("examinations: %s %s has no organisation; not applied", event.name, event.id)
        return IGNORED
    scope = resolve_organisation(db)
    if scope != organisation_id:
        # The relay runs the handler in the event's organisation. Anything else would write one organisation's event
        # under another's row-level security, or none: refuse rather than guess.
        raise RuntimeError("the session is not scoped to the event's organisation")
    if (event.version or 1) != SUPPORTED_VERSION:
        raise UnsupportedEventVersionError(f"{event.name}: envelope version {event.version} is not supported")
    payload = event.payload or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    seen = repo.ref_row(db, ProcessedEvent, ProcessedEvent.event_id, event.id, organisation_id)
    if seen is not None:
        return DUPLICATE
    # Recorded before the event is applied and flushed now, so the unique (organisation, event id) constraint settles two
    # deliveries racing: the loser's flush raises IntegrityError, the relay records the failure and redelivers, and the
    # redelivery finds the marker above. The marker lives in the handler's transaction: if anything below fails the
    # relay rolls the transaction back, marker included, and the redelivery applies the event.
    db.add(ProcessedEvent(organisation_id=organisation_id, event_id=event.id, name=event.name))
    db.flush()
    return apply(db, organisation_id, payload, _instant(event))


def _status_applies(row, occurred_at: datetime) -> bool:
    """A status from an event that occurred before the one that set the current status is stale. Equal times apply:
    they are the same change, or two changes the publisher cannot order, and the later delivery wins."""
    if row.status_as_of is None:
        return True
    known = row.status_as_of if row.status_as_of.tzinfo else row.status_as_of.replace(tzinfo=occurred_at.tzinfo)
    return occurred_at >= known


def _offering_row(db: Session, org: str, offering_id: str) -> OfferingRef:
    row = repo.ref_row(db, OfferingRef, OfferingRef.course_offering_id, offering_id, org)
    if row is None:
        row = OfferingRef(organisation_id=org, course_offering_id=offering_id)
        db.add(row)
    return row


def _offering_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    # Every field is validated before the row is touched, so a malformed event writes nothing.
    offering = _id(p, "course_offering_id")
    course = _id(p, "course_id")
    period = _id(p, "academic_period_id")
    code, title = _text(p, "course_code", 40), _text(p, "course_title", 200)
    credits = _credits(p)
    department = _id(p, "department_id") if p.get("department_id") is not None else None
    row = _offering_row(db, org, offering)
    if row.academic_period_id is not None:
        return IGNORED  # already created; the status a later event set is left alone
    row.course_id, row.academic_period_id, row.course_code, row.course_title = course, period, code, title
    row.credits, row.department_id = credits, department
    return APPLIED


def _offering_status_changed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    offering = _id(p, "course_offering_id")
    status = _text(p, "to_status", 20)
    row = _offering_row(db, org, offering)
    if not _status_applies(row, occurred_at):
        return STALE
    row.status, row.status_as_of = status, occurred_at
    return APPLIED


def on_offering_created(db: Session, event) -> str:
    return _receive(db, event, _offering_created)


def on_offering_status_changed(db: Session, event) -> str:
    return _receive(db, event, _offering_status_changed)


# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    OFFERING_CREATED: on_offering_created,
    OFFERING_STATUS_CHANGED: on_offering_status_changed,
}
