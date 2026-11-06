"""Use cases for scheduled classes, attendance sessions and attendance records (docs/prd.md FR-5 to FR-12,
contracts/openapi.yaml). They follow application/service.py: the domain decides, every state change publishes its
event and writes its audit entry in the same transaction and commits once, and any failure rolls all of it back.
`service.clock`, `service._publish` and `service._audit` are looked up on each call, so the tests' frozen clock and
injected failures reach these use cases too.

Who may act on a class (PRD section 12, contracts/permissions.yaml):
- open, close, mark and correct: the class's instructor (`instructor_id` is the caller's user id, pending the
  faculty-assignment identity mapping, docs/reviewer-decisions.md B); `attendance-session:override` widens them to
  every class of the organisation and lifts the marking window.
- reading sessions, records and their history: the instructor, or a holder of `report:read-all` or `override`.
- `report:read-department` and `attendance-record:correct-department` grant nothing more until the caller's department
  can be known (PRD Q9, reviewer decision A "Department scope").

Not here: generating classes from a timetable (it needs the organisation's time zone; see service.publish_timetable)
and closing open sessions automatically at their deadline (FR-11), which needs a scheduler job."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from types import SimpleNamespace

from eos_core.db import new_id
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import attendance as at
from ..domain import classes as cl
from ..domain import timetables as tt
from ..domain.errors import DomainRuleError
from ..domain.values import optional_label, require_choice, require_id, require_text
from ..infrastructure import attendance_repository as ar
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    AttendanceRecordChangeRow,
    AttendanceRecordRow,
    AttendanceSessionRow,
    ScheduledClassRow,
    as_utc,
    iso,
)
from . import access as k
from . import service as svc
from .access import Actor
from .errors import TimetableAttendanceError, forbidden, from_domain, invalid, not_found

_domain = svc._domain
transactional = svc.transactional


def _now() -> datetime:
    return as_utc(svc.clock())


def _policy() -> at.Policy:
    return load_settings().policy


# ---------------------------------------------------------------- request parsing


def _instant(value: object, field: str) -> tuple[datetime, tzinfo]:
    """A contract date-time with an offset, in UTC, and the offset it was given in. The offset names the wall clock
    the caller meant, so a class's date is read in it (the organisation's time zone has no source yet)."""
    if not isinstance(value, str):
        raise invalid("invalid_datetime", f"{field} must be a date and time with a zone", field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise invalid("invalid_datetime", f"{field} must be a date and time with a zone", field) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise invalid("invalid_datetime", f"{field} must be a date and time with a zone", field)
    return parsed.astimezone(UTC), parsed.tzinfo


def _id(value: object, field: str) -> str:
    return _domain(require_id, value, field)


# ---------------------------------------------------------------- rows and bodies


def class_domain(row: ScheduledClassRow) -> cl.ScheduledClass:
    return cl.ScheduledClass(
        id=row.id,
        academic_period_id=row.academic_period_id,
        course_offering_id=row.course_offering_id,
        section_id=row.section_id,
        instructor_assignment_id=row.instructor_assignment_id,
        instructor_id=row.instructor_id,
        class_date=row.class_date,
        starts_at=as_utc(row.starts_at),
        ends_at=as_utc(row.ends_at),
        timetable_id=row.timetable_id,
        slot_id=row.slot_id,
        location_label=row.location_label,
        status=row.status,
        cancel_reason=row.cancel_reason,
    )


def session_domain(row: AttendanceSessionRow) -> at.Session:
    return at.Session(
        id=row.id,
        scheduled_class_id=row.scheduled_class_id,
        opened_at=as_utc(row.opened_at),
        opened_by=row.opened_by,
        marking_deadline=as_utc(row.marking_deadline),
        status=row.status,
        closed_at=as_utc(row.closed_at),
        closed_by=row.closed_by,
    )


def class_bodies(db: Session, rows: list[ScheduledClassRow]) -> list[dict]:
    """components.schemas.ScheduledClass for each row; the course and section fields appear when the read models
    know them."""
    offerings = repo.offering_refs(db, {r.course_offering_id for r in rows})
    sections = ar.section_refs_any(db, {r.section_id for r in rows})
    sessions = ar.sessions_of_classes(db, [r.id for r in rows])
    bodies = []
    for row in rows:
        body: dict = {
            "id": row.id,
            "organisation_id": row.organisation_id,
            "timetable_id": row.timetable_id,
            "slot_id": row.slot_id,
            "academic_period_id": row.academic_period_id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "instructor_assignment_id": row.instructor_assignment_id,
            "instructor_id": row.instructor_id,
        }
        offering = offerings.get(row.course_offering_id)
        if offering is not None:
            if offering.course_code is not None:
                body["course_code"] = offering.course_code
            if offering.course_title is not None:
                body["course_title"] = offering.course_title
        section = sections.get(row.section_id)
        if section is not None:
            body["section_code"] = section.code
        session = sessions.get(row.id)
        body.update(
            {
                "class_date": iso(row.class_date),
                "starts_at": iso(row.starts_at),
                "ends_at": iso(row.ends_at),
                "location_label": row.location_label,
                "status": row.status,
                "cancel_reason": row.cancel_reason,
                "attendance_session": None if session is None else {"id": session.id, "status": session.status},
            }
        )
        bodies.append(body)
    return bodies


def class_body(db: Session, row: ScheduledClassRow) -> dict:
    return class_bodies(db, [row])[0]


def counts_of(records: list[AttendanceRecordRow]) -> dict[str, int]:
    """components.schemas.AttendanceCounts over a session's records (the eligible students' snapshot)."""
    return at.counts([r.student_id for r in records], {r.student_id: r.status for r in records if r.status})


def session_body(db: Session, row: AttendanceSessionRow) -> dict:
    """components.schemas.AttendanceSession"""
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "scheduled_class_id": row.scheduled_class_id,
        "status": row.status,
        "opened_at": iso(row.opened_at),
        "opened_by": row.opened_by,
        "marking_deadline": iso(row.marking_deadline),
        "closed_at": iso(row.closed_at),
        "closed_by": row.closed_by,
        "counts": counts_of(ar.records_of_session(db, row.id)),
    }


def record_bodies(db: Session, rows: list[AttendanceRecordRow]) -> list[dict]:
    """components.schemas.AttendanceRecord. A student not yet marked has no record in the contract's sense: `id` is
    null until a status is set (the stored row is the eligibility snapshot)."""
    names = ar.student_names(db, {r.student_id for r in rows})
    corrected = ar.corrected_record_ids(db, [r.id for r in rows])
    bodies = []
    for row in rows:
        body: dict = {
            "id": row.id if row.status is not None else None,
            "organisation_id": row.organisation_id,
            "attendance_session_id": row.attendance_session_id,
            "student_id": row.student_id,
        }
        if row.student_id in names:
            body["student_name"] = names[row.student_id]
        body.update(
            {
                "status": row.status,
                "remark": row.remark,
                "marked_by": row.marked_by,
                "marked_at": iso(row.marked_at),
                "corrected": row.id in corrected,
            }
        )
        bodies.append(body)
    return sorted(bodies, key=lambda b: (b.get("student_name") or "", b["student_id"]))


def _records_page(db: Session, session_id: str, status: str | None = None) -> dict:
    rows = ar.records_of_session(db, session_id)
    if status is not None:
        rows = [r for r in rows if r.status == status]
    items = record_bodies(db, rows)
    return {"attendance_session_id": session_id, "items": items, "total": len(items)}


# ---------------------------------------------------------------- lookups and scope


def _class(db: Session, class_id: str, *, lock: bool = False) -> ScheduledClassRow:
    row = ar.scheduled_class(db, class_id, lock=lock)
    if row is None:  # also another organisation's class: scoped queries cannot see it
        raise not_found("scheduled_class_not_found", "scheduled class not found")
    return row


def _session(db: Session, session_id: str, *, lock: bool = False) -> AttendanceSessionRow:
    row = ar.session(db, session_id, lock=lock)
    if row is None:
        raise not_found("attendance_session_not_found", "attendance session not found")
    return row


def _record(db: Session, record_id: str, *, lock: bool = False) -> AttendanceRecordRow:
    row = ar.record(db, record_id, lock=lock)
    if row is None:
        raise not_found("attendance_record_not_found", "attendance record not found")
    return row


def teaches(a: Actor, row: ScheduledClassRow) -> bool:
    return row.instructor_id == a.user_id


def _ensure_may_act(a: Actor, row: ScheduledClassRow) -> None:
    """Open, close and mark: the class's instructor, or `attendance-session:override`."""
    if not (teaches(a, row) or a.can(k.ATTENDANCE_SESSION_OVERRIDE)):
        raise forbidden("only the class's instructor, or a holder of attendance-session:override, may do this")


def _ensure_may_read(a: Actor, row: ScheduledClassRow) -> None:
    """Sessions, records and history: the class's instructor, or `report:read-all` / `override` (the department
    widening of `report:read-department` waits on PRD Q9)."""
    if not (teaches(a, row) or a.can(k.REPORT_READ_ALL) or a.can(k.ATTENDANCE_SESSION_OVERRIDE)):
        raise forbidden("only the class's instructor, or a holder of report:read-all, may read its attendance")


def _assignment(db: Session, offering_id: str, section_id: str, assignment_id: str):
    """The offering and the assignment, checked the way timetable slots are (422 when unknown or mismatched)."""
    offerings = repo.offering_refs(db, {offering_id})
    sections = repo.section_refs(db, {section_id})
    assignments = repo.assignment_refs(db, {assignment_id})
    _domain(
        tt.ensure_known_references,
        [
            SimpleNamespace(
                course_offering_id=offering_id, section_id=section_id, instructor_assignment_id=assignment_id
            )
        ],
        offerings=set(offerings),
        sections={sid: ref.course_offering_id for sid, ref in sections.items()},
        assignments={aid: (ref.course_offering_id, ref.section_id) for aid, ref in assignments.items()},
    )
    assignment = assignments[assignment_id]
    if assignment.status == "ended":
        raise TimetableAttendanceError(
            422,
            "assignment_ended",
            f"instructor assignment {assignment_id} has ended",
            field="instructor_assignment_id",
        )
    return offerings[offering_id], assignment


# ---------------------------------------------------------------- scheduled classes

CREATE_FIELDS = (
    "course_offering_id",
    "section_id",
    "instructor_assignment_id",
    "starts_at",
    "ends_at",
    "location_label",
)
UPDATE_FIELDS = ("starts_at", "ends_at", "location_label", "instructor_assignment_id", "reason")


def list_classes(db: Session, filters: dict, limit: int, offset: int) -> dict:
    """GET /scheduled-classes: the organisation's classes ordered by start time (scheduled-class:read is not limited
    to a scope by the PRD)."""
    for field in (
        "academic_period_id",
        "course_offering_id",
        "section_id",
        "instructor_id",
        "department_id",
        "timetable_id",
    ):
        if filters.get(field) is not None:
            _id(filters[field], field)
    first = svc._parse_date(filters["date_from"], "date_from") if filters.get("date_from") else None
    last = svc._parse_date(filters["date_to"], "date_to") if filters.get("date_to") else None
    if first and last and last < first:
        raise invalid("invalid_range", "date_to must not be before date_from", "date_to")
    if filters.get("status") is not None:
        _domain(require_choice, filters["status"], "status", cl.CLASS_STATUSES)
    offering_ids = None
    if filters.get("department_id") is not None:
        offering_ids = ar.offering_ids_of_department(db, filters["department_id"])
    rows, total = ar.classes(
        db,
        date_from=first,
        date_to=last,
        academic_period_id=filters.get("academic_period_id"),
        course_offering_id=filters.get("course_offering_id"),
        section_id=filters.get("section_id"),
        instructor_id=filters.get("instructor_id"),
        offering_ids=offering_ids,
        timetable_id=filters.get("timetable_id"),
        status=filters.get("status"),
        limit=limit,
        offset=offset,
    )
    return {"items": class_bodies(db, rows), "total": total}


def get_class(db: Session, class_id: str) -> dict:
    return class_body(db, _class(db, class_id))


def _class_created_payload(row: ScheduledClassRow) -> dict:
    return {
        "scheduled_class_id": row.id,
        "timetable_id": row.timetable_id,
        "academic_period_id": row.academic_period_id,
        "course_offering_id": row.course_offering_id,
        "section_id": row.section_id,
        "instructor_assignment_id": row.instructor_assignment_id,
        "instructor_id": row.instructor_id,
        "class_date": iso(row.class_date),
        "starts_at": iso(row.starts_at),
        "ends_at": iso(row.ends_at),
        "location_label": row.location_label,
    }


@transactional
def create_class(db: Session, a: Actor, body: object) -> dict:
    """POST /scheduled-classes (FR-5): an ad-hoc class (extra or make-up) with no slot. Its academic period and
    instructor come from the read models; its date is the start's date in the offset the request gives. Publishes
    scheduled-class.created."""
    data = svc._object(body, "body", CREATE_FIELDS)
    missing = [f for f in CREATE_FIELDS[:5] if f not in data]
    if missing:
        raise invalid("missing_field", f"{', '.join(missing)} is required", missing[0])
    offering_id = _id(data["course_offering_id"], "course_offering_id")
    section_id = _id(data["section_id"], "section_id")
    assignment_id = _id(data["instructor_assignment_id"], "instructor_assignment_id")
    start, zone = _instant(data["starts_at"], "starts_at")
    end, _ = _instant(data["ends_at"], "ends_at")
    _domain(cl.new_adhoc_window, start, end)
    location = _domain(optional_label, data.get("location_label"), "location_label")
    offering, assignment = _assignment(db, offering_id, section_id, assignment_id)
    created = _domain(
        cl.ScheduledClass,
        id=new_id(),
        academic_period_id=offering.academic_period_id,
        course_offering_id=offering_id,
        section_id=section_id,
        instructor_assignment_id=assignment_id,
        instructor_id=assignment.instructor_id,
        class_date=start.astimezone(zone).date(),
        starts_at=start,
        ends_at=end,
        location_label=location,
    )
    row = ScheduledClassRow(
        id=created.id,
        organisation_id=a.organisation_id,
        timetable_id=None,
        slot_id=None,
        academic_period_id=created.academic_period_id,
        course_offering_id=created.course_offering_id,
        section_id=created.section_id,
        instructor_assignment_id=created.instructor_assignment_id,
        instructor_id=created.instructor_id,
        class_date=created.class_date,
        starts_at=created.starts_at,
        ends_at=created.ends_at,
        location_label=created.location_label,
        status=created.status,
    )
    db.add(row)
    db.flush()
    payload = _class_created_payload(row)
    svc._publish(db, a, "scheduled-class.created", payload)
    after = {k_: v for k_, v in payload.items() if k_ != "scheduled_class_id"}
    svc._audit(db, a, "scheduled-class.created", "scheduled_class", row, after=after)
    db.commit()
    return class_body(db, row)


@transactional
def update_class(db: Session, a: Actor, class_id: str, body: object) -> dict:
    """PATCH /scheduled-classes/{id} (FR-5): reschedule a class, or change its location or instructor assignment (a
    substitute must be assigned to the same course offering and section). Refused with 409 once the class is
    cancelled or has a closed session. The class keeps its id and its old values stay in the audit entry. An open
    session's marking deadline follows a new end. Publishes scheduled-class.updated only when something changed."""
    data = svc._object(body, "body", UPDATE_FIELDS)
    row = _class(db, class_id, lock=True)
    session = ar.session_of_class(db, row.id, lock=True)
    reason = None if data.get("reason") is None else _domain(require_text, data["reason"], "reason", max_length=500)
    starts_at, zone = _instant(data["starts_at"], "starts_at") if data.get("starts_at") is not None else (None, UTC)
    ends_at = _instant(data["ends_at"], "ends_at")[0] if data.get("ends_at") is not None else None
    instructor = None
    if data.get("instructor_assignment_id") is not None:
        assignment_id = _id(data["instructor_assignment_id"], "instructor_assignment_id")
        _, assignment = _assignment(db, row.course_offering_id, row.section_id, assignment_id)
        instructor = (assignment_id, assignment.instructor_id)
    current = class_domain(row)
    updated, changed = _domain(
        cl.plan_reschedule,
        current,
        has_closed_session=session is not None and session.status == at.CLOSED,
        starts_at=starts_at,
        ends_at=ends_at,
        zone=zone,
        location_label=data["location_label"] if "location_label" in data else ...,
        instructor=instructor,
    )
    if changed:
        fields = list(changed)
        fields += ["class_date"] if "starts_at" in changed else []
        fields += ["instructor_id"] if "instructor_assignment_id" in changed else []
        before = {f: getattr(current, f) for f in fields}
        after = {f: getattr(updated, f) for f in fields}
        for f in fields:
            setattr(row, f, after[f])
        if "ends_at" in changed and session is not None and session.status == at.OPEN:
            session.marking_deadline = at.marking_window(updated, _policy()).closes_at
        svc._publish(
            db,
            a,
            "scheduled-class.updated",
            {
                "scheduled_class_id": row.id,
                "changed_fields": changed,
                "class_date": iso(updated.class_date),
                "starts_at": iso(updated.starts_at),
                "ends_at": iso(updated.ends_at),
                "location_label": updated.location_label,
            },
        )
        svc._audit(db, a, "scheduled-class.updated", "scheduled_class", row, before=before, after=after, reason=reason)
    db.commit()
    return class_body(db, row)


@transactional
def cancel_class(db: Session, a: Actor, class_id: str, body: object) -> dict:
    """POST /scheduled-classes/{id}/cancel (FR-5): refused with 409 once the class is cancelled or has a closed
    session. An open session is marked cancelled, not closed (reviewer decision), so no student becomes absent and
    the class never counts. Publishes scheduled-class.cancelled."""
    data = svc._object({} if body is None else body, "body", ("reason",))
    row = _class(db, class_id, lock=True)
    session = ar.session_of_class(db, row.id, lock=True)
    current = class_domain(row)
    cancelled = _domain(
        cl.plan_cancel,
        current,
        has_closed_session=session is not None and session.status == at.CLOSED,
        reason=data.get("reason"),
    )
    now = _now()
    row.status, row.cancel_reason = cancelled.status, cancelled.cancel_reason
    if session is not None and session.status == at.OPEN:
        session.status = _domain(at.plan_cancel_session, session_domain(session)).status
        svc._audit(
            db,
            a,
            "attendance-session.cancelled",
            "attendance_session",
            session,
            before={"status": at.OPEN},
            after={"status": session.status},
            reason=cancelled.cancel_reason,
        )
    svc._publish(
        db,
        a,
        "scheduled-class.cancelled",
        {
            "scheduled_class_id": row.id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "class_date": iso(row.class_date),
            "reason": row.cancel_reason,
            "cancelled_at": iso(now),
        },
    )
    svc._audit(
        db,
        a,
        "scheduled-class.cancelled",
        "scheduled_class",
        row,
        before={"status": current.status},
        after={"status": row.status, "cancel_reason": row.cancel_reason},
        reason=row.cancel_reason,
    )
    db.commit()
    return class_body(db, row)


# ---------------------------------------------------------------- attendance sessions


def get_session_of_class(db: Session, a: Actor, class_id: str) -> dict:
    row = _class(db, class_id)
    _ensure_may_read(a, row)
    session = ar.session_of_class(db, row.id)
    if session is None:
        raise not_found("attendance_session_not_found", "no attendance session has been opened for this class")
    return session_body(db, session)


def get_session(db: Session, a: Actor, session_id: str) -> dict:
    session = _session(db, session_id)
    _ensure_may_read(a, _class(db, session.scheduled_class_id))
    return session_body(db, session)


@transactional
def open_session(db: Session, a: Actor, class_id: str) -> tuple[dict, bool]:
    """POST /scheduled-classes/{id}/attendance-session (FR-7, FR-8). Returns (session, created). The class must be
    scheduled and now inside its marking window (`override` lifts the window); an open session is returned as it is.
    Opening snapshots the students allocated to the section on the class date as unmarked records. Publishes
    attendance-session.opened."""
    row = _class(db, class_id, lock=True)
    _ensure_may_act(a, row)
    existing = ar.session_of_class(db, row.id)
    now, policy = _now(), _policy()
    cls = class_domain(row)
    try:
        found = at.ensure_can_open(cls, None if existing is None else session_domain(existing), now, policy)
    except DomainRuleError as err:
        if not (err.code == "outside_marking_window" and a.can(k.ATTENDANCE_SESSION_OVERRIDE)):
            raise from_domain(err) from err
        found = None
    if found is not None:
        return session_body(db, existing), False
    session = AttendanceSessionRow(
        id=new_id(),
        organisation_id=a.organisation_id,
        scheduled_class_id=row.id,
        status=at.OPEN,
        opened_at=now,
        opened_by=a.user_id,
        marking_deadline=at.marking_window(cls, policy).closes_at,
    )
    db.add(session)
    try:
        db.flush()  # the first write of this transaction, so a whole rollback loses nothing else
    except IntegrityError as err:  # another request opened it first
        if not repo.is_session_conflict(err):
            raise
        db.rollback()
        return session_body(db, ar.session_of_class(db, row.id)), False
    members = ar.members_on(db, row.section_id, row.class_date)
    db.add_all(
        AttendanceRecordRow(
            organisation_id=a.organisation_id, attendance_session_id=session.id, student_id=m.student_id, status=None
        )
        for m in {m.student_id: m for m in members}.values()
    )
    db.flush()
    svc._publish(
        db,
        a,
        "attendance-session.opened",
        {
            "attendance_session_id": session.id,
            "scheduled_class_id": row.id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "class_date": iso(row.class_date),
            "eligible_count": len({m.student_id for m in members}),
            "marking_deadline": iso(session.marking_deadline),
        },
    )
    svc._audit(
        db,
        a,
        "attendance-session.opened",
        "attendance_session",
        session,
        after={"scheduled_class_id": row.id, "eligible_count": len({m.student_id for m in members})},
    )
    db.commit()
    return session_body(db, session), True


@transactional
def close_session(db: Session, a: Actor, session_id: str) -> dict:
    """POST /attendance-sessions/{id}/close (FR-11): unmarked eligible students become absent and the class becomes
    completed. Publishes attendance-session.closed with the final counts."""
    session = _session(db, session_id, lock=True)
    row = _class(db, session.scheduled_class_id, lock=True)
    _ensure_may_act(a, row)
    records = ar.records_of_session(db, session.id)
    now = _now()
    closed, unmarked = _domain(
        at.plan_close,
        session_domain(session),
        [r.student_id for r in records],
        {r.student_id: r.status for r in records if r.status},
        now=now,
        closed_by=a.user_id,
    )
    absent = set(unmarked)
    for r in records:
        if r.student_id in absent:
            r.status, r.marked_at = at.ABSENT, now
    session.status, session.closed_at, session.closed_by = closed.status, closed.closed_at, closed.closed_by
    row.status = cl.COMPLETED
    final = counts_of(records)
    svc._publish(
        db,
        a,
        "attendance-session.closed",
        {
            "attendance_session_id": session.id,
            "scheduled_class_id": row.id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "class_date": iso(row.class_date),
            "closed_by": closed.closed_by,
            "closed_at": iso(now),
            **{s: final[s] for s in at.ATTENDANCE_STATUSES},
        },
    )
    svc._audit(
        db,
        a,
        "attendance-session.closed",
        "attendance_session",
        session,
        before={"status": at.OPEN},
        after={"status": at.CLOSED, "marked_absent_at_close": len(absent), **final},
    )
    db.commit()
    return session_body(db, session)


# ---------------------------------------------------------------- attendance records


def list_records(db: Session, a: Actor, session_id: str, status: str | None) -> dict:
    """GET /attendance-sessions/{id}/records: every eligible student; unmarked ones have status null."""
    if status is not None:
        _domain(require_choice, status, "status", at.ATTENDANCE_STATUSES)
    session = _session(db, session_id)
    _ensure_may_read(a, _class(db, session.scheduled_class_id))
    return _records_page(db, session.id, status)


@transactional
def mark(db: Session, a: Actor, session_id: str, body: object) -> dict:
    """PUT /attendance-sessions/{id}/records (FR-9): set the listed eligible students' statuses in an open session,
    before its deadline (`override` lifts the deadline); others are left as they are. 422 lists the students that
    are not eligible. Publishes one attendance-record.marked per call."""
    data = svc._object(body, "body", ("records",))
    if "records" not in data:
        raise invalid("missing_field", "records is required", "records")
    marks = _domain(at.parse_marks, data["records"])
    session = _session(db, session_id, lock=True)
    row = _class(db, session.scheduled_class_id)
    _ensure_may_act(a, row)
    now = _now()
    try:
        at.ensure_can_mark(session_domain(session), now)
    except DomainRuleError as err:
        if not (err.code == "marking_window_ended" and a.can(k.ATTENDANCE_SESSION_OVERRIDE)):
            raise from_domain(err) from err
    records = {r.student_id: r for r in ar.records_of_session(db, session.id)}
    _domain(at.ensure_eligible, marks, records)
    for m in marks:
        r = records[m.student_id]
        r.status, r.remark, r.marked_by, r.marked_at = m.status, m.remark, a.user_id, now
    db.flush()
    svc._publish(
        db,
        a,
        "attendance-record.marked",
        {
            "attendance_session_id": session.id,
            "scheduled_class_id": row.id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "class_date": iso(row.class_date),
            "records": [
                {"attendance_record_id": records[m.student_id].id, "student_id": m.student_id, "status": m.status}
                for m in marks
            ],
        },
    )
    svc._audit(
        db,
        a,
        "attendance-record.marked",
        "attendance_session",
        session,
        after={"records": {m.student_id: m.status for m in marks}},
    )
    db.commit()
    return _records_page(db, session.id)


@transactional
def correct(db: Session, a: Actor, record_id: str, body: object) -> dict:
    """PATCH /attendance-records/{id} (FR-10): a record of a closed session changes only with a reason. The
    instructor may correct within the correction window, `override` any class at any time. The previous value goes
    to the record's history. Publishes attendance-record.updated."""
    data = svc._object(body, "body", ("status", "remark", "reason"))
    record = _record(db, record_id, lock=True)
    session = _session(db, record.attendance_session_id)
    row = _class(db, session.scheduled_class_id)
    if a.can(k.ATTENDANCE_SESSION_OVERRIDE):
        scope = at.ORGANISATION
    elif teaches(a, row):
        scope = at.INSTRUCTOR
    else:
        raise forbidden(
            "only the class's instructor, or a holder of attendance-session:override, may correct its records "
            "(the department scope of attendance-record:correct-department waits on PRD Q9)"
        )
    now = _now()
    change = _domain(
        at.plan_correction,
        session_domain(session),
        record.status,
        data.get("status"),
        data.get("reason"),
        data.get("remark"),
        scope=scope,
        now=now,
        policy=_policy(),
    )
    before = {"status": record.status}
    record.status = change.to_status
    if "remark" in data:
        record.remark = change.remark
    db.add(
        AttendanceRecordChangeRow(
            organisation_id=a.organisation_id,
            attendance_record_id=record.id,
            from_status=change.from_status,
            to_status=change.to_status,
            reason=change.reason,
            changed_by=a.user_id,
            changed_at=now,
        )
    )
    db.flush()
    svc._publish(
        db,
        a,
        "attendance-record.updated",
        {
            "attendance_record_id": record.id,
            "attendance_session_id": session.id,
            "course_offering_id": row.course_offering_id,
            "student_id": record.student_id,
            "class_date": iso(row.class_date),
            "from_status": change.from_status,
            "to_status": change.to_status,
            "reason": change.reason,
        },
    )
    svc._audit(
        db,
        a,
        "attendance-record.updated",
        "attendance_record",
        record,
        before=before,
        after={"status": record.status},
        reason=change.reason,
    )
    db.commit()
    return record_bodies(db, [record])[0]


def record_history(db: Session, a: Actor, record_id: str) -> dict:
    """GET /attendance-records/{id}/history: the corrections, oldest first."""
    record = _record(db, record_id)
    session = _session(db, record.attendance_session_id)
    _ensure_may_read(a, _class(db, session.scheduled_class_id))
    items = [
        {
            "id": c.id,
            "from_status": c.from_status,
            "to_status": c.to_status,
            "reason": c.reason,
            "changed_by": c.changed_by,
            "changed_at": iso(c.changed_at),
        }
        for c in ar.changes_of_record(db, record.id)
    ]
    return {"attendance_record_id": record.id, "items": items}


# ---------------------------------------------------------------- the caller's classes (widgets)


def day_or_today(value: str | None):
    """The `date` query parameter, or today. The contract says "today in the organisation's time zone"; no source for
    that zone exists yet (docs/reviewer-decisions.md section 10), so today is the UTC date, and the widgets pass the
    viewer's own date instead."""
    return svc._parse_date(value, "date") if value is not None else _now().date()


def teaching_schedule(db: Session, a: Actor, day: str | None) -> dict:
    """GET /me/teaching-schedule (FR-6): the classes the caller teaches on the date, every status, by start time."""
    on = day_or_today(day)
    return {"date": iso(on), "items": class_bodies(db, ar.classes_taught_on(db, a.user_id, on))}


def my_schedule(db: Session, a: Actor, day: str | None) -> dict:
    """GET /me/schedule (FR-6): the classes of the sections the caller is allocated to on the date. The caller's user
    id is taken as the `student_id` of the allocation read model (provisional, PRD Q3)."""
    on = day_or_today(day)
    sections = ar.sections_of_student_on(db, a.user_id, on)
    return {"date": iso(on), "items": class_bodies(db, ar.classes_of_sections_on(db, sections, on))}


def attendance_to_mark(db: Session, a: Actor) -> dict:
    """GET /me/attendance-to-mark (FR-12): the caller's classes that have started, are scheduled (not cancelled or
    completed), have no closed or cancelled session and are still inside the marking window, oldest first."""
    now, policy = _now(), _policy()
    window = timedelta(hours=policy.marking_window_hours)
    rows = ar.started_classes_taught(db, a.user_id, now, now - window)
    sessions = ar.sessions_of_classes(db, [r.id for r in rows])
    records = ar.records_of_sessions(db, [s.id for s in sessions.values()])
    pending = []
    for row in rows:
        session = sessions.get(row.id)
        if session is not None and session.status != at.OPEN:
            continue
        deadline = (
            as_utc(session.marking_deadline) if session else at.marking_window(class_domain(row), policy).closes_at
        )
        if now > deadline:
            continue
        pending.append((row, deadline, session))
    bodies = class_bodies(db, [row for row, _, _ in pending])
    items = []
    for body, (_, deadline, session) in zip(bodies, pending, strict=True):
        item: dict = {"scheduled_class": body, "marking_deadline": iso(deadline)}
        if session is not None:
            item["counts"] = counts_of(records.get(session.id, []))
        items.append(item)
    return {"items": items, "total": len(items)}
