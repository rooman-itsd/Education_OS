"""What lms consumes (event-bus entry point `eos.event_consumers`), kept as local read models (docs/prd.md sections 9,
10 and 12). The relay calls each handler with its own session, in the event's organisation, and commits afterwards
(platform/event-bus/README.md).

- `academic-management.offering.created`            -> offering_ref (course code, title, department, period)
- `academic-management.offering.status-changed`     -> offering_ref.status
- `academic-management.faculty-assignment.created`  -> instructor_ref, active (who teaches a course space)
- `academic-management.faculty-assignment.ended`    -> instructor_ref, ended
- `enrolment-registration.course-registration.confirmed` -> member_ref, active (who learns in a course space)
- `enrolment-registration.course-registration.withdrawn` -> member_ref, withdrawn
- `enrolment-registration.section-allocation.changed`    -> member_ref.section_id

`faculty_id` and `person_id` are read as identity user ids, the token subject, as academic-management reads
`faculty_id` (docs/prd.md LQ5, LQ6; README "Assumptions to revisit").

Delivery is at-least-once and unordered (platform/event-bus/contracts/events.yaml), so:
- each envelope id is recorded per organisation in `processed_event` before the event is applied, in the handler's
  transaction; a repeated id does nothing;
- a creation never overwrites what a later event already set, and an event that arrives before its creation leaves a
  partial row the creation completes;
- a status (or section) is replaced only by an event that occurred at or after the one that set it (envelope
  `occurred_at`, compared per row);
- an event is applied only in its own organisation; one with no organisation is not ours."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import InstructorRef, MemberRef, OfferingRef, ProcessedEvent, as_utc

log = logging.getLogger("eos.lms")

AM, ER = "academic-management", "enrolment-registration"
OFFERING_CREATED = f"{AM}.offering.created"
OFFERING_STATUS_CHANGED = f"{AM}.offering.status-changed"
ASSIGNMENT_CREATED = f"{AM}.faculty-assignment.created"
ASSIGNMENT_ENDED = f"{AM}.faculty-assignment.ended"
REGISTRATION_CONFIRMED = f"{ER}.course-registration.confirmed"
REGISTRATION_WITHDRAWN = f"{ER}.course-registration.withdrawn"
SECTION_CHANGED = f"{ER}.section-allocation.changed"

SUPPORTED_VERSION = 1
APPLIED, DUPLICATE, IGNORED, STALE = "applied", "duplicate", "ignored", "stale"
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class UnsupportedEventVersionError(ValueError):
    """The envelope's version is not one this module understands; the relay records the failure."""


def _id(p: dict, name: str, required: bool = True) -> str | None:
    """A uuid field. A malformed event is refused, never half applied: the ValueError reaches the relay, which records
    it and retries, then dead-letters."""
    value = p.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not UUID.match(value):
        raise ValueError(f"{name} must be a uuid")
    return value


def _text(p: dict, name: str, max_length: int, required: bool = True) -> str | None:
    value = p.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"{name} must be text of at most {max_length} characters")
    return value


def _instant(event) -> datetime:
    value = event.occurred_at
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        raise ValueError("occurred_at must be an instant")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _receive(db: Session, event, apply) -> str:
    organisation_id = event.organisation_id
    if not organisation_id:
        log.warning("lms: %s %s has no organisation; not applied", event.name, event.id)
        return IGNORED
    if resolve_organisation(db) != organisation_id:
        raise RuntimeError("the session is not scoped to the event's organisation")
    if (getattr(event, "version", 1) or 1) != SUPPORTED_VERSION:
        raise UnsupportedEventVersionError(f"{event.name}: envelope version {event.version} is not supported")
    payload = event.payload or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if repo.ref_row(db, ProcessedEvent, ProcessedEvent.event_id, event.id, organisation_id) is not None:
        return DUPLICATE
    db.add(ProcessedEvent(organisation_id=organisation_id, event_id=event.id, name=event.name))
    db.flush()
    return apply(db, organisation_id, payload, _instant(event))


def _newer(row, occurred_at: datetime) -> bool:
    """A change from an event older than the one that set the current state is stale."""
    return row.status_as_of is None or occurred_at >= as_utc(row.status_as_of)


def _row(db: Session, model, column, value: str, org: str, **defaults):
    row = repo.ref_row(db, model, column, value, org)
    if row is None:
        row = model(organisation_id=org, **{column.key: value}, **defaults)
        db.add(row)
    return row


# ---------------------------------------------------------------- academic-management


def _offering_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    offering = _id(p, "course_offering_id")
    facts = {
        "academic_period_id": _id(p, "academic_period_id"),
        "course_code": _text(p, "course_code", 40),
        "course_title": _text(p, "course_title", 200),
        "department_id": _id(p, "department_id", required=False),
    }
    row = _row(db, OfferingRef, OfferingRef.course_offering_id, offering, org)
    if row.academic_period_id is not None:
        return IGNORED
    for name, value in facts.items():
        setattr(row, name, value)
    return APPLIED


def _offering_status_changed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    row = _row(db, OfferingRef, OfferingRef.course_offering_id, _id(p, "course_offering_id"), org)
    status = _text(p, "to_status", 20)
    if not _newer(row, occurred_at):
        return STALE
    row.status, row.status_as_of = status, occurred_at
    return APPLIED


def _assignment(db: Session, org: str, p: dict, occurred_at: datetime, status: str) -> str:
    row = _row(
        db,
        InstructorRef,
        InstructorRef.instructor_assignment_id,
        _id(p, "instructor_assignment_id"),
        org,
        course_offering_id=_id(p, "course_offering_id"),
        instructor_id=_id(p, "faculty_id"),
        status=status,
    )
    row.section_id = _id(p, "section_id", required=False)
    if status == "active" and p.get("role") is not None:
        row.role = _text(p, "role", 40)
    if not _newer(row, occurred_at):
        return STALE  # an end that occurred later already arrived
    row.status, row.status_as_of = status, occurred_at
    return APPLIED


def _assignment_created(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    return _assignment(db, org, p, occurred_at, "active")


def _assignment_ended(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    return _assignment(db, org, p, occurred_at, "ended")


# ---------------------------------------------------------------- enrolment-registration


def _registration(
    db: Session, org: str, p: dict, occurred_at: datetime, status: str | None, section_field: str | None
) -> str:
    """A withdrawal names the section the registration had; it changes the status only."""
    row = _row(
        db,
        MemberRef,
        MemberRef.registration_id,
        _id(p, "registration_id"),
        org,
        course_offering_id=_id(p, "course_offering_id"),
        student_id=_id(p, "person_id"),
        status=status,
    )
    if p.get("student_name") is not None:
        row.student_name = _text(p, "student_name", 200)
    section = _id(p, section_field, required=False) if section_field else None
    if not _newer(row, occurred_at):
        return STALE
    if section is not None:
        row.section_id = section
    if status is not None:
        row.status = status
    row.status_as_of = occurred_at
    return APPLIED


def _registration_confirmed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    return _registration(db, org, p, occurred_at, "active", "section_id")


def _registration_withdrawn(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    _id(p, "section_id", required=False)
    return _registration(db, org, p, occurred_at, "withdrawn", None)


def _section_changed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    _id(p, "to_section_id")
    row = repo.ref_row(db, MemberRef, MemberRef.registration_id, _id(p, "registration_id"), org)
    status = None if row is not None else "active"  # a move before the confirmation implies the registration
    return _registration(db, org, p, occurred_at, status, "to_section_id")


def on_offering_created(db: Session, event) -> str:
    return _receive(db, event, _offering_created)


def on_offering_status_changed(db: Session, event) -> str:
    return _receive(db, event, _offering_status_changed)


def on_assignment_created(db: Session, event) -> str:
    return _receive(db, event, _assignment_created)


def on_assignment_ended(db: Session, event) -> str:
    return _receive(db, event, _assignment_ended)


def on_registration_confirmed(db: Session, event) -> str:
    return _receive(db, event, _registration_confirmed)


def on_registration_withdrawn(db: Session, event) -> str:
    return _receive(db, event, _registration_withdrawn)


def on_section_changed(db: Session, event) -> str:
    return _receive(db, event, _section_changed)


# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    OFFERING_CREATED: on_offering_created,
    OFFERING_STATUS_CHANGED: on_offering_status_changed,
    ASSIGNMENT_CREATED: on_assignment_created,
    ASSIGNMENT_ENDED: on_assignment_ended,
    REGISTRATION_CONFIRMED: on_registration_confirmed,
    REGISTRATION_WITHDRAWN: on_registration_withdrawn,
    SECTION_CHANGED: on_section_changed,
}
