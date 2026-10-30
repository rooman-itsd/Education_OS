"""Enrolment and registration use cases. Every function works inside the caller's transaction (routes commit),
filters every query by the caller's organisation, and writes an audit row plus, where contracts/events.yaml names
one, an outbox event in that same transaction. Event payloads never carry organisation_id: it is on the envelope
(platform/event-bus/contracts/events.yaml)."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime

import sqlalchemy as sa
from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import enums as e
from ..domain import rules
from ..domain.rules import OfferingSnapshot, RuleViolationError, SectionSnapshot, WindowSnapshot
from ..infrastructure.models import (
    AuditEntry,
    CourseRegistration,
    OfferingRef,
    ProgrammeEnrolment,
    RegistrationWindow,
    RollNumberCounter,
    SectionRef,
    TermRef,
    as_utc,
)

MODULE = "enrolment-registration"

CODE_STATUS = {
    "not_found": 404,
    "duplicate_enrolment": 409,
    "enrolment_ended": 409,
    "enrolment_not_active": 409,
    "already_registered": 409,
    "window_closed": 409,
    "offering_not_open": 409,
    "section_not_open": 409,
    "section_full": 409,
    "registration_not_confirmed": 409,
    "same_section": 409,
    "invalid_window": 422,
    "section_not_in_offering": 422,
    "term_mismatch": 422,
}


@dataclass
class Actor:
    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class EnrolmentError(Exception):
    """A refusal with an HTTP status and the contract's error body {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.status = CODE_STATUS.get(code, 422)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> EnrolmentError:
    return EnrolmentError("not_found", f"{what} not found")


def _check(rule, *args):
    try:
        return rule(*args)
    except RuleViolationError as v:
        raise EnrolmentError(v.code, v.message) from v


def _audit(db: Session, org: str, actor: str | None, action: str, entity: str, entity_id: str, detail=None) -> None:
    db.add(
        AuditEntry(organisation_id=org, actor=actor, action=action, entity=entity, entity_id=entity_id, detail=detail)
    )


def _publish(db: Session, org: str, actor: str | None, name: str, payload: dict) -> None:
    events.publish(db, f"{MODULE}.{name}", org, payload, actor)


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat() if isinstance(value, datetime) else value.isoformat()


def _like(term: str) -> str:
    """A contains-pattern for ilike with the caller's % _ \\ taken literally."""
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _locking(db: Session, query):
    """Row locks only where they exist; SQLite serialises writers anyway."""
    return query.with_for_update() if db.get_bind().dialect.name == "postgresql" else query


def _page(query, order_by, page: int, page_size: int):
    total = query.count()
    rows = query.order_by(*order_by).offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


# ---------------------------------------------------------------- programme enrolment


def _get_enrolment(db: Session, org: str, enrolment_id: str) -> ProgrammeEnrolment:
    row = (
        db.query(ProgrammeEnrolment)
        .filter(ProgrammeEnrolment.organisation_id == org, ProgrammeEnrolment.id == enrolment_id)
        .one_or_none()
    )
    if row is None:
        raise _not_found("programme enrolment")
    return row


def _roll_number_prefix() -> str:
    return os.environ.get("ENROLMENT_REGISTRATION_ROLL_NUMBER_PREFIX", "RN").strip() or "RN"


def _next_roll_number(db: Session, org: str, year: int) -> str:
    """Numbers per organisation and year, never reused; the counter row is locked on Postgres so two enrolments
    never get the same number."""
    counter = _locking(
        db,
        db.query(RollNumberCounter).filter(RollNumberCounter.organisation_id == org, RollNumberCounter.year == year),
    ).one_or_none()
    if counter is None:
        counter = RollNumberCounter(organisation_id=org, year=year, last_value=0)
        db.add(counter)
    counter.last_value += 1
    db.flush()
    return rules.format_roll_number(_roll_number_prefix(), year, counter.last_value)


def enrol(
    db: Session,
    actor: Actor,
    *,
    person_id: str,
    student_name: str,
    programme_id: str,
    start_academic_period_id: str,
    source_application_id: str | None = None,
) -> dict:
    org = actor.organisation_id
    active = db.query(ProgrammeEnrolment.id).filter(
        ProgrammeEnrolment.organisation_id == org,
        ProgrammeEnrolment.person_id == person_id,
        ProgrammeEnrolment.programme_id == programme_id,
        ProgrammeEnrolment.status == e.ACTIVE,
    )
    if active.first() is not None:
        raise EnrolmentError("duplicate_enrolment", "The person already has an active enrolment in this programme")
    now = utcnow()
    enrolment = ProgrammeEnrolment(
        organisation_id=org,
        person_id=person_id,
        student_name=student_name.strip(),
        programme_id=programme_id,
        roll_number=_next_roll_number(db, org, now.year),
        start_academic_period_id=start_academic_period_id,
        status=e.ACTIVE,
        source_application_id=source_application_id,
        enrolled_at=now,
        enrolled_by=actor.user_id,
    )
    db.add(enrolment)
    db.flush()
    _audit(
        db, org, actor.user_id, "enrolled", "programme_enrolment", enrolment.id, {"roll_number": enrolment.roll_number}
    )
    _publish(
        db,
        org,
        actor.user_id,
        "programme-enrolment.created",
        {
            "programme_enrolment_id": enrolment.id,
            "person_id": enrolment.person_id,
            "programme_id": enrolment.programme_id,
            "roll_number": enrolment.roll_number,
            "start_academic_period_id": enrolment.start_academic_period_id,
            "student_name": enrolment.student_name,
            "enrolled_at": _iso(now),
        },
    )
    db.flush()
    return enrolment.to_dict()


def list_enrolments(
    db: Session,
    actor: Actor,
    *,
    programme_id: str | None = None,
    person_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    query = db.query(ProgrammeEnrolment).filter(ProgrammeEnrolment.organisation_id == actor.organisation_id)
    if programme_id:
        query = query.filter(ProgrammeEnrolment.programme_id == programme_id)
    if person_id:
        query = query.filter(ProgrammeEnrolment.person_id == person_id)
    if status:
        query = query.filter(ProgrammeEnrolment.status == status)
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.filter(
            sa.or_(
                ProgrammeEnrolment.student_name.ilike(pattern, escape="\\"),
                ProgrammeEnrolment.roll_number.ilike(pattern, escape="\\"),
            )
        )
    rows, total = _page(query, (ProgrammeEnrolment.enrolled_at.desc(), ProgrammeEnrolment.id), page, page_size)
    return {"items": [r.to_dict() for r in rows], "total": total, "page": page, "page_size": page_size}


def get_enrolment(db: Session, actor: Actor, enrolment_id: str) -> dict:
    return _get_enrolment(db, actor.organisation_id, enrolment_id).to_dict()


def withdraw_enrolment(db: Session, actor: Actor, enrolment_id: str, reason: str) -> dict:
    """Withdraws every confirmed registration first, each with its own event, then the enrolment."""
    enrolment = _get_enrolment(db, actor.organisation_id, enrolment_id)
    _check(rules.check_can_end, enrolment.status)
    reason = reason.strip()
    now = utcnow()
    confirmed = (
        db.query(CourseRegistration)
        .filter(
            CourseRegistration.organisation_id == enrolment.organisation_id,
            CourseRegistration.programme_enrolment_id == enrolment.id,
            CourseRegistration.status == e.CONFIRMED,
        )
        .order_by(CourseRegistration.confirmed_at, CourseRegistration.id)
        .all()
    )
    for registration in confirmed:
        _withdraw(db, actor, registration, reason, now)
    enrolment.status = e.WITHDRAWN
    enrolment.ended_at = now
    enrolment.end_reason = reason
    _audit(db, enrolment.organisation_id, actor.user_id, "enrolment_withdrawn", "programme_enrolment", enrolment.id)
    _publish(
        db,
        enrolment.organisation_id,
        actor.user_id,
        "programme-enrolment.withdrawn",
        {
            "programme_enrolment_id": enrolment.id,
            "person_id": enrolment.person_id,
            "programme_id": enrolment.programme_id,
            "reason": reason,
            "withdrawn_at": _iso(now),
        },
    )
    db.flush()
    return enrolment.to_dict()


def complete_enrolment(db: Session, actor: Actor, enrolment_id: str) -> dict:
    """No event: contracts/events.yaml publishes none for completion."""
    enrolment = _get_enrolment(db, actor.organisation_id, enrolment_id)
    _check(rules.check_can_end, enrolment.status)
    enrolment.status = e.COMPLETED
    enrolment.ended_at = utcnow()
    _audit(db, enrolment.organisation_id, actor.user_id, "enrolment_completed", "programme_enrolment", enrolment.id)
    db.flush()
    return enrolment.to_dict()


# ---------------------------------------------------------------- registration windows


def _window_row(db: Session, org: str, term: str) -> RegistrationWindow | None:
    return (
        db.query(RegistrationWindow)
        .filter(RegistrationWindow.organisation_id == org, RegistrationWindow.academic_period_id == term)
        .one_or_none()
    )


def _snapshot(window: RegistrationWindow | None) -> WindowSnapshot | None:
    if window is None:
        return None
    return WindowSnapshot(opens_at=as_utc(window.opens_at), closes_at=as_utc(window.closes_at))


def _window_view(window: RegistrationWindow) -> dict:
    return window.to_dict() | {"is_open": rules.is_window_open(_snapshot(window), utcnow())}


def get_window(db: Session, actor: Actor, academic_period_id: str) -> dict:
    window = _window_row(db, actor.organisation_id, academic_period_id)
    if window is None:
        raise _not_found("registration window")
    return _window_view(window)


def set_window(db: Session, actor: Actor, academic_period_id: str, opens_at: datetime, closes_at: datetime) -> dict:
    _check(rules.validate_window, opens_at, closes_at)
    org = actor.organisation_id
    window = _window_row(db, org, academic_period_id)
    if window is None:
        window = RegistrationWindow(organisation_id=org, academic_period_id=academic_period_id)
        db.add(window)
    window.opens_at = opens_at
    window.closes_at = closes_at
    window.updated_by = actor.user_id
    window.updated_at = utcnow()
    db.flush()
    _audit(
        db,
        org,
        actor.user_id,
        "window_set",
        "registration_window",
        window.id,
        {"academic_period_id": academic_period_id, "opens_at": _iso(opens_at), "closes_at": _iso(closes_at)},
    )
    db.flush()
    return _window_view(window)


# ---------------------------------------------------------------- course registration


def _offering(db: Session, org: str, offering_id: str) -> OfferingSnapshot | None:
    row = (
        db.query(OfferingRef)
        .filter(OfferingRef.organisation_id == org, OfferingRef.course_offering_id == offering_id)
        .one_or_none()
    )
    return OfferingSnapshot(row.course_offering_id, row.academic_period_id, row.status) if row else None


def _section(db: Session, org: str, section_id: str) -> SectionSnapshot | None:
    """Locks the section's copy on Postgres while its seats are counted, so two registrations never take the last
    seat."""
    row = _locking(
        db, db.query(SectionRef).filter(SectionRef.organisation_id == org, SectionRef.section_id == section_id)
    ).one_or_none()
    return SectionSnapshot(row.section_id, row.course_offering_id, row.capacity, row.status) if row else None


def _seats_taken(db: Session, org: str, section_id: str) -> int:
    return (
        db.query(sa.func.count(CourseRegistration.id))
        .filter(
            CourseRegistration.organisation_id == org,
            CourseRegistration.section_id == section_id,
            CourseRegistration.status == e.CONFIRMED,
        )
        .scalar()
    )


def _registered(db: Session, org: str, person_id: str, offering_id: str) -> bool:
    return (
        db.query(CourseRegistration.id)
        .filter(
            CourseRegistration.organisation_id == org,
            CourseRegistration.person_id == person_id,
            CourseRegistration.course_offering_id == offering_id,
            CourseRegistration.status == e.CONFIRMED,
        )
        .first()
        is not None
    )


def _place(
    db: Session,
    actor: Actor,
    enrolment: ProgrammeEnrolment,
    *,
    course_offering_id: str,
    section_id: str,
    academic_period_id: str,
    registration_type: str,
) -> CourseRegistration:
    """Rules 1 to 5 in the contract's order; nothing is written unless every check passes."""
    org = enrolment.organisation_id
    now = utcnow()
    _check(rules.check_enrolment_active, enrolment.status)
    if _registered(db, org, enrolment.person_id, course_offering_id):
        raise EnrolmentError("already_registered", "The student already has a confirmed registration for this offering")
    _check(rules.check_window, registration_type, _snapshot(_window_row(db, org, academic_period_id)), now)
    offering = _offering(db, org, course_offering_id)
    _check(rules.check_offering, offering, academic_period_id)
    section = _section(db, org, section_id)
    _check(rules.check_section, section, course_offering_id, _seats_taken(db, org, section_id))

    registration = CourseRegistration(
        organisation_id=org,
        programme_enrolment_id=enrolment.id,
        person_id=enrolment.person_id,
        course_offering_id=course_offering_id,
        section_id=section_id,
        academic_period_id=academic_period_id,
        registration_type=registration_type,
        status=e.CONFIRMED,
        references_verified=rules.references_verified(offering, section),
        section_since=now.date(),
        confirmed_at=now,
        confirmed_by=actor.user_id,
    )
    db.add(registration)
    db.flush()
    _audit(
        db,
        org,
        actor.user_id,
        "registration_confirmed",
        "course_registration",
        registration.id,
        {"course_offering_id": course_offering_id, "section_id": section_id, "registration_type": registration_type},
    )
    _publish(
        db,
        org,
        actor.user_id,
        "course-registration.confirmed",
        {
            "registration_id": registration.id,
            "person_id": registration.person_id,
            "course_offering_id": course_offering_id,
            "section_id": section_id,
            "academic_period_id": academic_period_id,
            "registration_type": registration_type,
            "student_name": enrolment.student_name,
            "roll_number": enrolment.roll_number,
            "confirmed_at": _iso(now),
        },
    )
    db.flush()
    return registration


def _withdraw(db: Session, actor: Actor, registration: CourseRegistration, reason: str, now: datetime) -> None:
    registration.status = e.WITHDRAWN
    registration.withdrawn_at = now
    registration.withdrawn_by = actor.user_id
    registration.withdrawal_reason = reason
    _audit(
        db,
        registration.organisation_id,
        actor.user_id,
        "registration_withdrawn",
        "course_registration",
        registration.id,
    )
    _publish(
        db,
        registration.organisation_id,
        actor.user_id,
        "course-registration.withdrawn",
        {
            "registration_id": registration.id,
            "person_id": registration.person_id,
            "course_offering_id": registration.course_offering_id,
            "section_id": registration.section_id,
            "reason": reason,
            "withdrawn_at": _iso(now),
        },
    )
    db.flush()


def _views(db: Session, registrations: Iterable[CourseRegistration]) -> list[dict]:
    """Contract CourseRegistration: each row plus its enrolment's name and roll number, in one extra query."""
    registrations = list(registrations)
    ids = {r.programme_enrolment_id for r in registrations}
    enrolments = (
        {en.id: en for en in db.query(ProgrammeEnrolment).filter(ProgrammeEnrolment.id.in_(ids))} if ids else {}
    )
    return [
        r.to_dict()
        | {
            "student_name": enrolments[r.programme_enrolment_id].student_name,
            "roll_number": enrolments[r.programme_enrolment_id].roll_number,
        }
        for r in registrations
    ]


def _get_registration(db: Session, org: str, registration_id: str) -> CourseRegistration:
    row = (
        db.query(CourseRegistration)
        .filter(CourseRegistration.organisation_id == org, CourseRegistration.id == registration_id)
        .one_or_none()
    )
    if row is None:
        raise _not_found("course registration")
    return row


def register(
    db: Session,
    actor: Actor,
    *,
    programme_enrolment_id: str,
    course_offering_id: str,
    section_id: str,
    academic_period_id: str,
    registration_type: str = e.REGULAR,
) -> dict:
    enrolment = _get_enrolment(db, actor.organisation_id, programme_enrolment_id)
    registration = _place(
        db,
        actor,
        enrolment,
        course_offering_id=course_offering_id,
        section_id=section_id,
        academic_period_id=academic_period_id,
        registration_type=registration_type,
    )
    return _views(db, [registration])[0]


def register_bulk(
    db: Session,
    actor: Actor,
    *,
    programme_enrolment_ids: list[str],
    course_offering_id: str,
    section_id: str,
    academic_period_id: str,
    registration_type: str = e.REGULAR,
) -> dict:
    """One result per student, in request order. Seats taken earlier in the batch count against the capacity."""
    results = []
    for enrolment_id in programme_enrolment_ids:
        try:
            # One savepoint per student: a unique-index race on one row (a registration confirmed by another
            # request between the check and the insert) refuses that student and never fails the batch.
            with db.begin_nested():
                enrolment = _get_enrolment(db, actor.organisation_id, enrolment_id)
                registration = _place(
                    db,
                    actor,
                    enrolment,
                    course_offering_id=course_offering_id,
                    section_id=section_id,
                    academic_period_id=academic_period_id,
                    registration_type=registration_type,
                )
                db.flush()
        except EnrolmentError as refusal:
            results.append(
                {
                    "programme_enrolment_id": enrolment_id,
                    "outcome": "refused",
                    "registration": None,
                    "code": refusal.code,
                    "message": refusal.message,
                }
            )
            continue
        except IntegrityError:
            results.append(
                {
                    "programme_enrolment_id": enrolment_id,
                    "outcome": "refused",
                    "registration": None,
                    "code": "already_registered",
                    "message": "The student already has a confirmed registration for this offering",
                }
            )
            continue
        results.append(
            {
                "programme_enrolment_id": enrolment_id,
                "outcome": "confirmed",
                "registration": _views(db, [registration])[0],
                "code": None,
                "message": None,
            }
        )
    confirmed = sum(1 for r in results if r["outcome"] == "confirmed")
    return {"confirmed": confirmed, "refused": len(results) - confirmed, "results": results}


def list_registrations(
    db: Session,
    actor: Actor,
    *,
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    section_id: str | None = None,
    person_id: str | None = None,
    programme_enrolment_id: str | None = None,
    registration_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    query = db.query(CourseRegistration).filter(CourseRegistration.organisation_id == actor.organisation_id)
    for column, value in (
        (CourseRegistration.academic_period_id, academic_period_id),
        (CourseRegistration.course_offering_id, course_offering_id),
        (CourseRegistration.section_id, section_id),
        (CourseRegistration.person_id, person_id),
        (CourseRegistration.programme_enrolment_id, programme_enrolment_id),
        (CourseRegistration.registration_type, registration_type),
        (CourseRegistration.status, status),
    ):
        if value:
            query = query.filter(column == value)
    rows, total = _page(query, (CourseRegistration.confirmed_at.desc(), CourseRegistration.id), page, page_size)
    return {"items": _views(db, rows), "total": total, "page": page, "page_size": page_size}


def get_registration(db: Session, actor: Actor, registration_id: str) -> dict:
    return _views(db, [_get_registration(db, actor.organisation_id, registration_id)])[0]


def withdraw_registration(db: Session, actor: Actor, registration_id: str, reason: str) -> dict:
    registration = _get_registration(db, actor.organisation_id, registration_id)
    _check(rules.check_registration_confirmed, registration.status)
    _withdraw(db, actor, registration, reason.strip(), utcnow())
    return _views(db, [registration])[0]


def change_section(db: Session, actor: Actor, registration_id: str, to_section_id: str, effective_on: date) -> dict:
    org = actor.organisation_id
    registration = _get_registration(db, org, registration_id)
    _check(rules.check_registration_confirmed, registration.status)
    _check(rules.check_section_change, registration.section_id, to_section_id)
    section = _section(db, org, to_section_id)
    _check(rules.check_section, section, registration.course_offering_id, _seats_taken(db, org, to_section_id))
    from_section_id = registration.section_id
    registration.section_id = to_section_id
    registration.section_since = effective_on
    # The flag describes the registration's current references: a move to a known section verifies it, a move to
    # a section this module has no copy of yet does not.
    registration.references_verified = rules.references_verified(
        _offering(db, org, registration.course_offering_id), section
    )
    enrolment = _get_enrolment(db, org, registration.programme_enrolment_id)
    _audit(
        db,
        org,
        actor.user_id,
        "section_changed",
        "course_registration",
        registration.id,
        {"from_section_id": from_section_id, "to_section_id": to_section_id, "effective_on": effective_on.isoformat()},
    )
    _publish(
        db,
        org,
        actor.user_id,
        "section-allocation.changed",
        {
            "registration_id": registration.id,
            "person_id": registration.person_id,
            "course_offering_id": registration.course_offering_id,
            "from_section_id": from_section_id,
            "to_section_id": to_section_id,
            "effective_on": effective_on.isoformat(),
            "student_name": enrolment.student_name,
        },
    )
    db.flush()
    return _views(db, [registration])[0]


# ---------------------------------------------------------------- report


def registered_candidates(db: Session, actor: Actor, *, academic_period_id: str | None = None, limit: int = 5) -> dict:
    """The term asked for, else the active term from the local copy, else every term (academic_period_id null)."""
    org = actor.organisation_id
    term_id = academic_period_id
    if term_id is None:
        active = db.query(TermRef).filter(TermRef.organisation_id == org, TermRef.is_active.is_(True)).first()
        term_id = active.academic_period_id if active else None
    query = db.query(
        CourseRegistration.course_offering_id,
        CourseRegistration.registration_type,
        sa.func.count(CourseRegistration.id),
    ).filter(CourseRegistration.organisation_id == org, CourseRegistration.status == e.CONFIRMED)
    if term_id:
        query = query.filter(CourseRegistration.academic_period_id == term_id)
    by_type = {t: 0 for t in e.REGISTRATION_TYPES}
    per_offering: dict[str, int] = {}
    for offering_id, registration_type, count in query.group_by(
        CourseRegistration.course_offering_id, CourseRegistration.registration_type
    ):
        by_type[registration_type] = by_type.get(registration_type, 0) + count
        per_offering[offering_id] = per_offering.get(offering_id, 0) + count
    ranked = rules.rank_offerings(per_offering, limit)
    names = {
        r.course_offering_id: r
        for r in db.query(OfferingRef).filter(
            OfferingRef.organisation_id == org, OfferingRef.course_offering_id.in_([o for o, _ in ranked])
        )
    }
    term = (
        db.query(TermRef).filter(TermRef.organisation_id == org, TermRef.academic_period_id == term_id).one_or_none()
        if term_id
        else None
    )
    return {
        "academic_period_id": term_id,
        "term_name": term.name if term else None,
        "total": sum(per_offering.values()),
        "by_type": by_type,
        "offerings": [
            {
                "course_offering_id": offering_id,
                "course_code": names[offering_id].course_code if offering_id in names else None,
                "course_title": names[offering_id].course_title if offering_id in names else None,
                "registered": count,
            }
            for offering_id, count in ranked
        ],
    }
