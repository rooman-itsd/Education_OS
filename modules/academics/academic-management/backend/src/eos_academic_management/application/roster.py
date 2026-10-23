"""The roster read model (FR-14): one row per course registration, kept from enrolment-registration's events.
academic-management never writes enrolment itself; it records what enrolment-registration decided.

Agreed with enrolment-registration (issue #100), pending its published events.yaml:
- events `enrolment-registration.course-registration.confirmed`, `.course-registration.withdrawn` and
  `.section-allocation.changed`, payload version 1;
- `person_id` is the learner's Person id from student-information; `course_offering_id` and `section_id` are this
  module's ids; a registration belongs to exactly one section and keeps one `registration_id` throughout;
- a withdrawal marks the row withdrawn and never deletes it; `roll_number` is optional;
- registrations are accepted only into an open offering and a section that is open and not full.

Delivery is at-least-once and `occurred_at` is not an ordering key (platform/event-bus/contracts/events.yaml), so:
- each envelope id is applied at most once (academic_management_processed_event);
- out-of-order delivery is handled only through what the agreement guarantees: a withdrawn registration is never
  re-enrolled by a late confirmation, a withdrawal that arrives before its confirmation is kept as a withdrawn row,
  and a section change applies only to a registration still in `from_section_id`. No sequence number is assumed."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.offerings import OPEN, SECTION_OPEN
from ..infrastructure import repository as repo
from ..infrastructure.models import OfferingRow, ProcessedEventRow, RosterEntryRow, SectionRow

SOURCE = "enrolment-registration"
CONFIRMED = f"{SOURCE}.course-registration.confirmed"
WITHDRAWN = f"{SOURCE}.course-registration.withdrawn"
SECTION_CHANGED = f"{SOURCE}.section-allocation.changed"
HANDLED = (CONFIRMED, WITHDRAWN, SECTION_CHANGED)
SUPPORTED_VERSION = 1

# Outcomes, returned to the caller (and the relay, once it exists) for logging.
APPLIED, DUPLICATE, IGNORED, STALE = "applied", "duplicate", "ignored", "stale"
REJECTED_OFFERING_NOT_OPEN = "rejected:offering_not_open"
REJECTED_SECTION_CLOSED = "rejected:section_closed"
REJECTED_SECTION_FULL = "rejected:section_full"
REJECTED_UNKNOWN_SECTION = "rejected:unknown_section"
REJECTED_MALFORMED_PAYLOAD = "rejected:malformed_payload"  # a required payload field is missing


def _time(value: object, fallback: object) -> datetime:
    raw = value if value is not None else fallback
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return utcnow()


def _admit(db: Session, offering_id: str, section_id: str, registration_id: str) -> str | None:
    """None when a registration may join the section, else the rejection outcome. The section row is locked first
    (SELECT ... FOR UPDATE), so two registrations into one section are checked one after the other on PostgreSQL;
    handle_event also re-counts after writing, before committing."""
    section = repo.section_for_update(db, section_id)
    offering = repo.get(db, OfferingRow, offering_id)
    if offering is None or section is None or section.course_offering_id != offering_id:
        return REJECTED_UNKNOWN_SECTION
    if offering.status != OPEN:
        return REJECTED_OFFERING_NOT_OPEN
    if section.status != SECTION_OPEN:
        return REJECTED_SECTION_CLOSED
    taken = [
        e
        for e in db.scalars(
            repo.q(db, RosterEntryRow).where(
                RosterEntryRow.section_id == section_id, RosterEntryRow.status == repo.ENROLLED
            )
        )
        if e.registration_id != registration_id
    ]
    if len(taken) >= section.capacity:
        return REJECTED_SECTION_FULL
    return None


def handle_event(db: Session, envelope: dict) -> str:
    """Apply one delivered event and commit. Events outside the three agreed names, or of a payload version this
    module does not understand, are ignored, as the envelope contract requires. The tenant is the envelope's
    organisation_id: every read and write is scoped to it."""
    name = envelope.get("name")
    if name not in HANDLED or envelope.get("version", 1) != SUPPORTED_VERSION:
        return IGNORED
    organisation_id = envelope.get("organisation_id")
    if not organisation_id:
        return IGNORED  # enrolment always happens inside an organisation
    db.info["organisation_id"] = organisation_id
    event_id = envelope["id"]
    if repo.processed(db, event_id) is not None:
        return DUPLICATE
    payload = envelope.get("payload") or {}
    occurred_at = envelope.get("occurred_at")
    handler = {CONFIRMED: _confirmed, WITHDRAWN: _withdrawn, SECTION_CHANGED: _section_changed}[name]
    try:
        outcome, admitted_to = handler(db, organisation_id, payload, occurred_at)
    except KeyError:
        # A payload missing an agreed field can never be applied; redelivering it would only fail the same way,
        # so the rejection is recorded like the others and the envelope id is not applied again.
        db.rollback()
        db.info["organisation_id"] = organisation_id
        outcome, admitted_to = REJECTED_MALFORMED_PAYLOAD, None
    if admitted_to is not None and _over_capacity(db, admitted_to):
        # A concurrent registration took the last seat between the check and this write: undo this one.
        db.rollback()
        db.info["organisation_id"] = organisation_id
        outcome = REJECTED_SECTION_FULL
    db.add(ProcessedEventRow(organisation_id=organisation_id, event_id=event_id, name=name, processed_at=utcnow()))
    db.commit()
    return outcome


def _over_capacity(db: Session, section_id: str) -> bool:
    """Re-count the section inside the same transaction, after this event's write is flushed."""
    db.flush()
    section = repo.get(db, SectionRow, section_id)
    return section is not None and repo.enrolled_in_section(db, section_id) > section.capacity


def _confirmed(db: Session, organisation_id: str, p: dict, occurred_at: object) -> tuple[str, str | None]:
    entry = repo.roster_entry(db, p["registration_id"])
    if entry is not None and entry.status == repo.WITHDRAWN:
        return STALE, None  # the withdrawal of this registration was already applied
    if entry is not None:
        entry.person_id = p["person_id"]
        entry.student_name = p.get("student_name", entry.student_name)
        entry.roll_number = p.get("roll_number", entry.roll_number)
        return APPLIED, None  # an enrolled row (from a section change that arrived first) keeps its section
    rejected = _admit(db, p["course_offering_id"], p["section_id"], p["registration_id"])
    if rejected:
        return rejected, None
    db.add(
        RosterEntryRow(
            organisation_id=organisation_id,
            registration_id=p["registration_id"],
            person_id=p["person_id"],
            course_offering_id=p["course_offering_id"],
            section_id=p["section_id"],
            student_name=p.get("student_name"),
            roll_number=p.get("roll_number"),
            status=repo.ENROLLED,
            enrolled_at=_time(p.get("confirmed_at"), occurred_at),
        )
    )
    return APPLIED, p["section_id"]


def _withdrawn(db: Session, organisation_id: str, p: dict, occurred_at: object) -> tuple[str, str | None]:
    entry = repo.roster_entry(db, p["registration_id"])
    withdrawn_at = _time(p.get("withdrawn_at"), occurred_at)
    if entry is None:
        # The withdrawal arrived before its confirmation: keep it, so the late confirmation is recognised as stale.
        # The section must be this organisation's and belong to the offering named, as _admit checks for the other
        # events; the row's offering is the section's, so the foreign key always holds.
        section = repo.get(db, SectionRow, p["section_id"])
        if section is None or section.course_offering_id != p["course_offering_id"]:
            return REJECTED_UNKNOWN_SECTION, None
        db.add(
            RosterEntryRow(
                organisation_id=organisation_id,
                registration_id=p["registration_id"],
                person_id=p["person_id"],
                course_offering_id=section.course_offering_id,
                section_id=section.id,
                status=repo.WITHDRAWN,
                enrolled_at=withdrawn_at,
                withdrawn_at=withdrawn_at,
            )
        )
        return APPLIED, None
    if entry.status == repo.WITHDRAWN:
        return APPLIED, None  # already withdrawn: the same state again
    entry.status, entry.withdrawn_at = repo.WITHDRAWN, withdrawn_at
    return APPLIED, None


def _section_changed(db: Session, organisation_id: str, p: dict, occurred_at: object) -> tuple[str, str | None]:
    entry = repo.roster_entry(db, p["registration_id"])
    if entry is not None and entry.status == repo.WITHDRAWN:
        return STALE, None
    if entry is not None and entry.section_id != p["from_section_id"]:
        return STALE, None  # the registration is no longer in the section this change starts from
    rejected = _admit(db, p["course_offering_id"], p["to_section_id"], p["registration_id"])
    if rejected:
        return rejected, None
    if entry is None:
        # The change arrived before its confirmation: record the registration in its new section; the confirmation
        # then only fills in the remaining fields.
        db.add(
            RosterEntryRow(
                organisation_id=organisation_id,
                registration_id=p["registration_id"],
                person_id=p["person_id"],
                course_offering_id=p["course_offering_id"],
                section_id=p["to_section_id"],
                status=repo.ENROLLED,
                enrolled_at=_time(None, occurred_at),
            )
        )
        return APPLIED, p["to_section_id"]
    entry.section_id = p["to_section_id"]
    return APPLIED, p["to_section_id"]
