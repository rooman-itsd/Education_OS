"""What timetable-attendance consumes (event-bus entry point `eos.event_consumers`): academic-management's term,
offering and section events and enrolment-registration's course-registration and section-allocation events, kept as
local read models (PRD sections 8 and 9). The relay calls each handler with its
own session, in the event's organisation, and commits afterwards (platform/event-bus/README.md).

Implemented here:
- `academic-management.term.created`            -> term_ref
- `academic-management.offering.created`        -> offering_ref (course and period facts)
- `academic-management.offering.status-changed` -> offering_ref.status
- `academic-management.section.created`         -> section_ref (code)
- `academic-management.section.updated`         -> section_ref.status
- `enrolment-registration.course-registration.confirmed` -> registration_ref, then section_member
- `enrolment-registration.course-registration.withdrawn` -> registration_ref.withdrawn_on, then section_member
- `enrolment-registration.section-allocation.changed`    -> registration_ref.moves, then section_member
- `student-information.person.account-linked`            -> person_account (which person a sign-in account is; a
  student's own `/me` reads map their user id to the `student_id` of section_member through it)

Not consumed, on purpose (docs/reviewer-decisions.md):
- `faculty-assignment.*`: storing the assignee as an instructor needs Faizan's confirmation of the identity mapping
  (`faculty_id` against `instructor_id`).
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
from datetime import date, datetime, timedelta

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..domain.errors import DomainRuleError
from ..domain.values import require_date, require_id, require_instant, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    OfferingRef,
    PersonAccount,
    ProcessedEvent,
    RegistrationRef,
    SectionMember,
    SectionRef,
    TermRef,
    as_utc,
)
from . import auto_close

log = logging.getLogger("eos.timetable_attendance")

SCHEDULER_JOB_DUE = "scheduler.job.due"
SOURCE = "academic-management"
TERM_CREATED = f"{SOURCE}.term.created"
OFFERING_CREATED = f"{SOURCE}.offering.created"
OFFERING_STATUS_CHANGED = f"{SOURCE}.offering.status-changed"
SECTION_CREATED = f"{SOURCE}.section.created"
SECTION_UPDATED = f"{SOURCE}.section.updated"
ENROLMENT = "enrolment-registration"
REGISTRATION_CONFIRMED = f"{ENROLMENT}.course-registration.confirmed"
REGISTRATION_WITHDRAWN = f"{ENROLMENT}.course-registration.withdrawn"
SECTION_ALLOCATION_CHANGED = f"{ENROLMENT}.section-allocation.changed"
ACCOUNT_LINKED = "student-information.person.account-linked"

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


# ---------------------------------------------------------------- enrolment-registration -> section_member
#
# Who is in which section, and from when to when (FR-7). Each event adds one fact to the registration's
# `registration_ref`; the registration's `section_member` rows are then rebuilt from all its facts, so the result does
# not depend on the order the events arrive in:
# - confirmed: in `section_id` from the date of `confirmed_at`;
# - section-allocation.changed: out of the old section the day before `effective_on`, in `to_section_id` from it;
# - withdrawn: every membership ends on the date of `withdrawn_at` (inclusive).
# A fact already known is not replaced by a later copy (a second confirmation, a withdrawal twice, the same move
# twice). `person_id` is stored as the `student_id` (PRD Q3, enrolment-registration's integration points).


def _event_date(payload: dict, name: str) -> date:
    """The calendar date of a date-time field, read in the offset it carries (the wall clock of the publisher)."""
    value = payload.get(name)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{name} must be a date and time") from None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a date and time with a zone")
    return value.date()


def _registration(db: Session, org: str, p: dict) -> RegistrationRef:
    """The registration's read-model row, created with its student and offering on the first event that names it."""
    registration_id, student, offering = _id(p, "registration_id"), _id(p, "person_id"), _id(p, "course_offering_id")
    row = repo.ref_row(db, RegistrationRef, RegistrationRef.registration_id, registration_id, org)
    if row is None:
        row = RegistrationRef(
            organisation_id=org,
            registration_id=registration_id,
            student_id=student,
            course_offering_id=offering,
            moves=[],
        )
        db.add(row)
    elif (row.student_id, row.course_offering_id) != (student, offering):
        raise ValueError("a registration has one student and one course offering; the event names others")
    return row


def _name(row: RegistrationRef, p: dict, occurred_at: datetime) -> None:
    """The display name from the latest event that carries one (PRD Q3: the allocation events provide it)."""
    if p.get("student_name") is None:
        return
    name = _text(p, "student_name", 200)
    known = row.name_as_of
    if known is not None and known.tzinfo is None:
        known = known.replace(tzinfo=occurred_at.tzinfo)
    if known is None or occurred_at >= known:
        row.student_name, row.name_as_of = name, occurred_at


def memberships(row: RegistrationRef) -> list[tuple[str, date, date | None]]:
    """(section, from, to) of a registration from its facts, in time order; `to` None while it is open. Without the
    confirmation, the first section's start is unknown, so the memberships begin at the first move."""
    found: list[tuple[str, date, date | None]] = []
    section, start = row.section_id, row.confirmed_on
    for move in sorted(row.moves or [], key=lambda m: (m["on"], m["from"], m["to"])):
        on = date.fromisoformat(move["on"])
        if section is not None and start is not None:
            found.append((section, start, on - timedelta(days=1)))
        section, start = move["to"], on
    if section is not None and start is not None:
        found.append((section, start, None))
    if row.withdrawn_on is not None:
        end = row.withdrawn_on
        found = [(s, a, end if b is None or b > end else b) for s, a, b in found if a <= end]
    return [(s, a, b) for s, a, b in found if b is None or b >= a]


def _rebuild(db: Session, org: str, row: RegistrationRef) -> None:
    """Make the registration's section_member rows match its facts: rows are updated in place, added or removed. A row
    another registration already holds for the same student, section and start date is left to that registration."""
    db.flush()
    wanted = {(s, a): b for s, a, b in memberships(row)}
    existing = list(
        db.scalars(
            repo.q(db, SectionMember).where(
                SectionMember.organisation_id == org, SectionMember.registration_id == row.registration_id
            )
        )
    )
    for member in existing:
        key = (member.section_id, member.allocated_from)
        if key in wanted:
            member.allocated_to, member.student_name = wanted.pop(key), row.student_name
        else:
            db.delete(member)
    db.flush()
    for (section, start), end in sorted(wanted.items(), key=lambda kv: kv[0][1]):
        taken = db.scalars(
            repo.q(db, SectionMember).where(
                SectionMember.organisation_id == org,
                SectionMember.section_id == section,
                SectionMember.student_id == row.student_id,
                SectionMember.allocated_from == start,
            )
        ).first()
        if taken is not None:
            log.warning("timetable-attendance: a membership of another registration holds %s from %s", section, start)
            continue
        db.add(
            SectionMember(
                organisation_id=org,
                section_id=section,
                student_id=row.student_id,
                student_name=row.student_name,
                allocated_from=start,
                allocated_to=end,
                registration_id=row.registration_id,
            )
        )


def _registration_confirmed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    section, on = _id(p, "section_id"), _event_date(p, "confirmed_at")
    row = _registration(db, org, p)
    _name(row, p, occurred_at)
    if row.confirmed_on is not None:
        _rebuild(db, org, row)  # the name may have changed
        return IGNORED  # a registration is confirmed once; a second confirmation changes nothing
    row.section_id, row.confirmed_on = section, on
    _rebuild(db, org, row)
    return APPLIED


def _registration_withdrawn(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    _id(p, "section_id")
    on = _event_date(p, "withdrawn_at")
    row = _registration(db, org, p)
    if row.withdrawn_on is not None:
        return IGNORED
    row.withdrawn_on = on
    _rebuild(db, org, row)
    return APPLIED


def _section_allocation_changed(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    move = {
        "from": _id(p, "from_section_id"),
        "to": _id(p, "to_section_id"),
        "on": _date(p, "effective_on").isoformat(),
    }
    row = _registration(db, org, p)
    _name(row, p, occurred_at)
    if move in (row.moves or []):
        _rebuild(db, org, row)
        return IGNORED
    row.moves = [*(row.moves or []), move]  # a new list, so the JSON column is seen as changed
    _rebuild(db, org, row)
    return APPLIED


# ---------------------------------------------------------------- student-information -> person_account


def _account_linked(db: Session, org: str, p: dict, occurred_at: datetime) -> str:
    """Set the person's sign-in account: the user id when linked, none when the link is cleared. One row per person,
    replaced only by an event that occurred at or after the one that set it (a republish of the same link applies and
    changes nothing)."""
    person = _id(p, "person_id")
    linked = p.get("linked")
    if not isinstance(linked, bool):
        raise ValueError("linked must be true or false")
    user = _id(p, "identity_user_id") if linked else None
    row = repo.ref_row(db, PersonAccount, PersonAccount.person_id, person, org)
    if row is None:
        row = PersonAccount(organisation_id=org, person_id=person)
        db.add(row)
    elif row.linked_as_of is not None and occurred_at < as_utc(row.linked_as_of):
        return STALE
    row.identity_user_id, row.linked_as_of = user, occurred_at
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


def on_registration_confirmed(db: Session, event) -> str:
    return _receive(db, event, _registration_confirmed)


def on_registration_withdrawn(db: Session, event) -> str:
    return _receive(db, event, _registration_withdrawn)


def on_section_allocation_changed(db: Session, event) -> str:
    return _receive(db, event, _section_allocation_changed)


def on_account_linked(db: Session, event) -> str:
    return _receive(db, event, _account_linked)


def on_job_due(db: Session, event) -> str:
    """`scheduler.job.due` for this module's own job (FR-11); another module's job is not ours and is not recorded."""
    if not isinstance(event.payload, dict) or event.payload.get("job") != auto_close.JOB_KEY:
        return IGNORED
    return _receive(db, event, auto_close.run)


# Registered in pyproject.toml under `eos.event_consumers`; module.yaml `consumes_events` lists the same names.
CONSUMERS = {
    SCHEDULER_JOB_DUE: on_job_due,
    TERM_CREATED: on_term_created,
    OFFERING_CREATED: on_offering_created,
    OFFERING_STATUS_CHANGED: on_offering_status_changed,
    SECTION_CREATED: on_section_created,
    SECTION_UPDATED: on_section_updated,
    REGISTRATION_CONFIRMED: on_registration_confirmed,
    REGISTRATION_WITHDRAWN: on_registration_withdrawn,
    SECTION_ALLOCATION_CHANGED: on_section_allocation_changed,
    ACCOUNT_LINKED: on_account_linked,
}
