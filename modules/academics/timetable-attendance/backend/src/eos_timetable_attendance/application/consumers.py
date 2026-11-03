"""What timetable-attendance consumes (event-bus entry point `eos.event_consumers`): academic-management's term,
offering and section events, kept as local read models (PRD sections 8 and 9). The relay calls each handler with its
own session, in the event's organisation, and commits afterwards (platform/event-bus/README.md).

Implemented here:
- `academic-management.term.created`            -> term_ref
- `academic-management.offering.created`        -> offering_ref (course and period facts)
- `academic-management.offering.status-changed` -> offering_ref.status
- `academic-management.section.created`         -> section_ref (code)
- `academic-management.section.updated`         -> section_ref.status

Not consumed, on purpose (docs/reviewer-decisions.md):
- `faculty-assignment.*`: storing the assignee as an instructor needs Faizan's confirmation of the identity mapping
  (`faculty_id` against `instructor_id`).
- `enrolment-registration.*` (section members): they depend on the unconfirmed `student_id` mapping.
- `offering.updated` and `course.*`: their payloads carry only `changed_fields`, not the new values.

Delivery is at-least-once and unordered (platform/event-bus/contracts/events.yaml), so:
- Idempotency is keyed on the envelope id, recorded per organisation in `processed_event` before the event is applied;
  a repeated id does nothing. The marker is written in the handler's own transaction, so a failure rolls it back and the
  redelivery applies the event. Two deliveries racing for one id are settled by the table's unique constraint: the loser
  fails and is redelivered as a duplicate.
- A creation never overwrites what a later event already set, and an event that arrives before its creation leaves a
  partial row that the creation completes (the row is *known* only then).
- A status is replaced only by an event that occurred at or after the one that set it. The envelope `occurred_at` is
  the ordering key the event-bus contract points consumers to ("the entity's own state or occurred_at"); it is
  compared per row, never across rows or modules, and arrival order is never used.
- An event is applied only in its own organisation: the session scope must be the event's organisation, every read
  names the organisation, and rows are written with it. An event with no organisation is not ours."""

from __future__ import annotations

import logging
from datetime import date, datetime

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..domain.errors import DomainRuleError
from ..domain.values import require_date, require_id, require_instant, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import OfferingRef, ProcessedEvent, SectionRef, TermRef

log = logging.getLogger("eos.timetable_attendance")

SOURCE = "academic-management"
TERM_CREATED = f"{SOURCE}.term.created"
OFFERING_CREATED = f"{SOURCE}.offering.created"
OFFERING_STATUS_CHANGED = f"{SOURCE}.offering.status-changed"
SECTION_CREATED = f"{SOURCE}.section.created"
SECTION_UPDATED = f"{SOURCE}.section.updated"

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


def _date(payload: dict, name: str) -> date:
    """A date: an ISO `YYYY-MM-DD` string (a published payload is JSON) or a date."""
    value = payload.get(name)
    if isinstance(value, str) and len(value) == 10:
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{name} must be a date") from None
    return _field({name: value}, name, require_date)


def _instant(event) -> datetime:
    try:
        return require_instant(event.occurred_at, "occurred_at")
    except DomainRuleError as err:
        raise ValueError(f"occurred_at: {err.message}") from err


def _receive(db: Session, event, apply) -> str:
    """The common path of every handler: check the envelope, record the id, apply once."""
    organisation_id = event.organisation_id
    if not organisation_id:
        log.warning("timetable-attendance: %s %s has no organisation; not applied", event.name, event.id)
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


def _term_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    period = _id(p, "academic_period_id")
    starts, ends = _date(p, "starts_on"), _date(p, "ends_on")
    if ends < starts:
        raise ValueError("ends_on must not be before starts_on")
    if repo.ref_row(db, TermRef, TermRef.academic_period_id, period, org) is not None:
        return IGNORED  # a term's dates are set by its creation; a second creation event changes nothing
    db.add(
        TermRef(
            organisation_id=org,
            academic_period_id=period,
            code=_text(p, "code", 40),
            name=_text(p, "name", 200),
            starts_on=starts,
            ends_on=ends,
        )
    )
    return APPLIED


def _offering_row(db: Session, org: str, offering_id: str) -> OfferingRef:
    row = repo.ref_row(db, OfferingRef, OfferingRef.course_offering_id, offering_id, org)
    if row is None:
        row = OfferingRef(organisation_id=org, course_offering_id=offering_id)
        db.add(row)
    return row


def _offering_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    offering = _id(p, "course_offering_id")
    period = _id(p, "academic_period_id")
    code, title = _text(p, "course_code", 40), _text(p, "course_title", 200)
    department = _id(p, "department_id") if p.get("department_id") is not None else None
    row = _offering_row(db, org, offering)
    if row.academic_period_id is not None:
        return IGNORED  # already created; the status a later event set is left alone
    row.academic_period_id, row.course_code, row.course_title, row.department_id = period, code, title, department
    return APPLIED


def _offering_status_changed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    offering = _id(p, "course_offering_id")
    status = _text(p, "to_status", 20)
    row = _offering_row(db, org, offering)
    if not _status_applies(row, occurred_at):
        return STALE
    row.status, row.status_as_of = status, occurred_at
    return APPLIED


def _section_row(db: Session, org: str, section_id: str, offering_id: str) -> SectionRef:
    row = repo.ref_row(db, SectionRef, SectionRef.section_id, section_id, org)
    if row is None:
        row = SectionRef(organisation_id=org, section_id=section_id, course_offering_id=offering_id)
        db.add(row)
    elif row.course_offering_id != offering_id:
        raise ValueError("a section belongs to one course offering; the event names another")
    return row


def _section_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    section = _id(p, "section_id")
    row = _section_row(db, org, section, _id(p, "course_offering_id"))
    if row.code is not None:
        return IGNORED
    row.code = _text(p, "code", 40)
    return APPLIED


def _section_updated(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    section = _id(p, "section_id")
    status = _text(p, "status", 20)
    row = _section_row(db, org, section, _id(p, "course_offering_id"))
    if not _status_applies(row, occurred_at):
        return STALE
    row.status, row.status_as_of = status, occurred_at
    return APPLIED


def on_term_created(db: Session, event) -> str:
    return _receive(db, event, _term_created)


def on_offering_created(db: Session, event) -> str:
    return _receive(db, event, _offering_created)


def on_offering_status_changed(db: Session, event) -> str:
    return _receive(db, event, _offering_status_changed)


def on_section_created(db: Session, event) -> str:
    return _receive(db, event, _section_created)


def on_section_updated(db: Session, event) -> str:
    return _receive(db, event, _section_updated)


# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    TERM_CREATED: on_term_created,
    OFFERING_CREATED: on_offering_created,
    OFFERING_STATUS_CHANGED: on_offering_status_changed,
    SECTION_CREATED: on_section_created,
    SECTION_UPDATED: on_section_updated,
}
