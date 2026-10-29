"""Consumers of academic-management's events, keeping this module's local copies of terms, offerings and sections
(docs/integration-points.md). The event relay (platform/event-bus) will call handle_event with each envelope;
until it exists nothing calls it outside tests.

Delivery is at-least-once and unordered (platform/event-bus/contracts/events.yaml), so each envelope id is applied
once per organisation, a later field never resets one already known, and an event for a row of another
organisation is never applied."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..domain import enums as e
from ..infrastructure.models import OfferingRef, ProcessedEvent, SectionRef, TermRef

SUPPORTED_VERSION = 1
APPLIED, DUPLICATE, IGNORED = "applied", "duplicate", "ignored"


def _date(value) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _own(row, org: str):
    """A copy row of another organisation is never touched (ids are global, so this only guards bad input)."""
    return row if row is None or row.organisation_id == org else False


def _term_created(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(TermRef, p["academic_period_id"]), org)
    if row is False:
        return IGNORED
    if row is None:
        row = TermRef(academic_period_id=p["academic_period_id"], organisation_id=org, is_active=False)
        db.add(row)
    row.code, row.name = p.get("code"), p.get("name")
    row.starts_on, row.ends_on = _date(p.get("starts_on")), _date(p.get("ends_on"))
    return APPLIED


def _term_activated(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(TermRef, p["academic_period_id"]), org)
    if row is False:
        return IGNORED
    if row is None:
        row = TermRef(academic_period_id=p["academic_period_id"], organisation_id=org, is_active=False)
        db.add(row)
    db.query(TermRef).filter(
        TermRef.organisation_id == org, TermRef.academic_period_id != row.academic_period_id
    ).update({TermRef.is_active: False}, synchronize_session="fetch")
    row.is_active = True
    return APPLIED


def _offering_created(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(OfferingRef, p["course_offering_id"]), org)
    if row is False:
        return IGNORED
    if row is None:
        # academic-management FR-9: offerings start planned. A status that arrived first is kept.
        row = OfferingRef(course_offering_id=p["course_offering_id"], organisation_id=org, status="planned")
        db.add(row)
    row.academic_period_id = p["academic_period_id"]
    row.course_code, row.course_title = p.get("course_code"), p.get("course_title")
    return APPLIED


def _offering_status_changed(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(OfferingRef, p["course_offering_id"]), org)
    if not row:
        # Unknown offering: the payload has no term to create it with; offering.created brings it later.
        return IGNORED
    row.status = p["to_status"]
    return APPLIED


def _offering_updated(db: Session, org: str, p: dict) -> str:
    """Its payload names changed fields, not their values: nothing to copy."""
    return IGNORED


def _section_created(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(SectionRef, p["section_id"]), org)
    if row is False:
        return IGNORED
    if row is None:
        row = SectionRef(section_id=p["section_id"], organisation_id=org, status=e.OPEN, capacity=p["capacity"])
        db.add(row)
    row.course_offering_id, row.code = p["course_offering_id"], p.get("code")
    return APPLIED


def _section_updated(db: Session, org: str, p: dict) -> str:
    row = _own(db.get(SectionRef, p["section_id"]), org)
    if row is False:
        return IGNORED
    if row is None:
        row = SectionRef(section_id=p["section_id"], organisation_id=org, course_offering_id=p["course_offering_id"])
        db.add(row)
    row.capacity, row.status = p["capacity"], p["status"]
    return APPLIED


HANDLERS = {
    "academic-management.term.created": _term_created,
    "academic-management.term.activated": _term_activated,
    "academic-management.offering.created": _offering_created,
    "academic-management.offering.updated": _offering_updated,
    "academic-management.offering.status-changed": _offering_status_changed,
    "academic-management.section.created": _section_created,
    "academic-management.section.updated": _section_updated,
}


def handle_event(db: Session, envelope: dict) -> str:
    """Apply one envelope; returns applied, duplicate or ignored. The caller commits."""
    handler = HANDLERS.get(envelope.get("name"))
    org = envelope.get("organisation_id")
    if handler is None or org is None or envelope.get("version", 1) != SUPPORTED_VERSION:
        return IGNORED
    db.info["organisation_id"] = org
    event_id = str(envelope["id"])
    seen = db.query(ProcessedEvent.id).filter(
        ProcessedEvent.organisation_id == org, ProcessedEvent.event_id == event_id
    )
    if seen.first() is not None:
        return DUPLICATE
    outcome = handler(db, org, envelope.get("payload") or {})
    db.add(ProcessedEvent(organisation_id=org, event_id=event_id, name=envelope["name"]))
    db.flush()
    return outcome
