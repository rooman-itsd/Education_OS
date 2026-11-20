"""Attendance reports (docs/prd.md FR-13, FR-14, FR-18; contracts/openapi.yaml `reports` and `/me`). Read-only:
computed from the records, never stored.

What counts (FR-13, owner decision C7): the records of *closed* sessions of classes that are not cancelled. Open
sessions are not counted until they close; a cancelled session (its class was cancelled) never counts. `attended` is
present plus late; excused classes leave the denominator. A group with no counted class has a null percentage and is
never short (reviewer decision A, section 1).

The academic period defaults to the active one: the known term (`term_ref`) whose dates contain today's UTC date.
Without one, the summary and department report answer 404 `active_term_not_found`, as academic-management does for its
term-scoped reads. The history has no default period: without one it covers every period.

Access: a student reads their own data through `/me` (the caller's user id is the `student_id`, provisional PRD Q3).
`report:read-department` cannot be applied until the caller's department is known (PRD Q9, reviewer decision A
"Department scope"), so the `/reports` paths serve holders of `report:read-all` and refuse the others with 403
`department_unknown`."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..domain import reports as rp
from ..domain.values import require_id
from ..infrastructure import attendance_repository as ar
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import iso
from . import access as k
from . import service as svc
from .access import Actor
from .classes import _now, my_student_ids
from .errors import TimetableAttendanceError, invalid, not_found

_domain = svc._domain
TWO_PLACES = Decimal("0.01")
MAX_STUDENTS = 2000  # contract AttendanceEligibilityRequest.student_ids maxItems


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _threshold() -> int:
    return load_settings().shortage_threshold_percent


def _date(value: str | None, field: str) -> date | None:
    return None if value is None else svc._parse_date(value, field)


def _range(first: date | None, last: date | None, last_field: str = "date_to") -> None:
    if first is not None and last is not None and last < first:
        raise invalid("invalid_range", f"{last_field} must not be before the start of the range", last_field)


def _period(db: Session, academic_period_id: str | None) -> str:
    """The given academic period, or the active term (404 `active_term_not_found` when no known term is active)."""
    if academic_period_id is not None:
        return _domain(require_id, academic_period_id, "academic_period_id")
    term = ar.active_term(db, _now().date())
    if term is None:
        raise not_found("active_term_not_found", "academic_period_id was not given and no term is active today")
    return term.academic_period_id


def _department_unknown() -> TimetableAttendanceError:
    return TimetableAttendanceError(
        403,
        "department_unknown",
        "department reports need the caller's department, which cannot be known yet (PRD Q9); "
        "report:read-all holders may name any department",
    )


def _require_read_all(a: Actor) -> None:
    if not a.can(k.REPORT_READ_ALL):
        raise _department_unknown()


# ---------------------------------------------------------------- student summary and history


def _ids(student: str | tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """The student id a report names, and every id their records may be kept under (my_student_ids)."""
    ids = (student,) if isinstance(student, str) else student
    return ids[0], ids


def _summary(db: Session, student: str | tuple[str, ...], period: str) -> dict:
    """components.schemas.StudentAttendanceSummary: one row per course offering of the period."""
    student_id, ids = _ids(student)
    threshold = _threshold()
    statuses: dict[str, list[str]] = defaultdict(list)
    section_of: dict[str, str] = {}
    for record, _, cls in ar.attendance(db, academic_period_id=period, student_id=ids):
        statuses[cls.course_offering_id].append(record.status)
        section_of.setdefault(cls.course_offering_id, cls.section_id)  # newest class first: the latest section
    offerings = repo.offering_refs(db, set(statuses))
    items, overall = [], rp.Tally()
    for offering_id, found in statuses.items():
        t = rp.tally(found)
        overall = overall.plus(t)
        item: dict = {"course_offering_id": offering_id}
        ref = offerings.get(offering_id)
        if ref is not None and ref.course_code is not None:
            item["course_code"] = ref.course_code
        if ref is not None and ref.course_title is not None:
            item["course_title"] = ref.course_title
        item.update(
            {
                "section_id": section_of[offering_id],
                "classes_held": t.held,
                "attended": t.attended,
                "excused": t.excused,
                "percentage": _number(t.percentage),
                "below_threshold": t.below(threshold),
            }
        )
        items.append(item)
    items.sort(key=lambda i: (i.get("course_code") or "", i["course_offering_id"]))
    return {
        "student_id": student_id,
        "academic_period_id": period,
        "threshold_percent": threshold,
        "overall_percentage": _number(overall.percentage),
        "items": items,
    }


def _history(
    db: Session,
    student: str | tuple[str, ...],
    *,
    academic_period_id: str | None,
    course_offering_id: str | None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int,
    offset: int,
) -> dict:
    """components.schemas.StudentAttendanceHistory, newest first."""
    student_id, ids = _ids(student)
    if academic_period_id is not None:
        _domain(require_id, academic_period_id, "academic_period_id")
    if course_offering_id is not None:
        _domain(require_id, course_offering_id, "course_offering_id")
    first, last = _date(date_from, "date_from"), _date(date_to, "date_to")
    _range(first, last)
    rows = ar.attendance(
        db,
        academic_period_id=academic_period_id,
        course_offering_id=course_offering_id,
        student_id=ids,
        date_from=first,
        date_to=last,
    )
    page = rows[offset : offset + limit]
    offerings = repo.offering_refs(db, {c.course_offering_id for _, _, c in page})
    corrected = ar.corrected_record_ids(db, [r.id for r, _, _ in page])
    items = []
    for record, _, cls in page:
        item: dict = {"scheduled_class_id": cls.id, "course_offering_id": cls.course_offering_id}
        ref = offerings.get(cls.course_offering_id)
        if ref is not None and ref.course_code is not None:
            item["course_code"] = ref.course_code
        item.update(
            {
                "class_date": iso(cls.class_date),
                "starts_at": iso(cls.starts_at),
                "status": record.status,
                "corrected": record.id in corrected,
            }
        )
        items.append(item)
    return {"student_id": student_id, "items": items, "total": len(rows)}


def my_summary(db: Session, a: Actor, academic_period_id: str | None) -> dict:
    """GET /me/attendance-summary (FR-13)."""
    return _summary(db, my_student_ids(db, a), _period(db, academic_period_id))


def my_history(
    db: Session, a: Actor, academic_period_id: str | None, course_offering_id: str | None, limit: int, offset: int
) -> dict:
    """GET /me/attendance-history (FR-13)."""
    return _history(
        db,
        my_student_ids(db, a),
        academic_period_id=academic_period_id,
        course_offering_id=course_offering_id,
        limit=limit,
        offset=offset,
    )


def student_summary(db: Session, a: Actor, student_id: str, academic_period_id: str | None) -> dict:
    """GET /reports/students/{id}/attendance-summary (FR-13): report:read-all only until PRD Q9."""
    _domain(require_id, student_id, "student_id")
    _require_read_all(a)
    return _summary(db, student_id, _period(db, academic_period_id))


def student_history(db: Session, a: Actor, student_id: str, filters: dict, limit: int, offset: int) -> dict:
    """GET /reports/students/{id}/attendance-history (FR-13): report:read-all only until PRD Q9."""
    _domain(require_id, student_id, "student_id")
    _require_read_all(a)
    return _history(db, student_id, **filters, limit=limit, offset=offset)


# ---------------------------------------------------------------- department


def _flag(value: str | None, field: str) -> bool:
    if value is None:
        return False
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    raise invalid("invalid_boolean", f"{field} must be true or false", field)


def _mean(values: list[Decimal]) -> float | None:
    if not values:
        return None
    return float((sum(values) / len(values)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def department_attendance(
    db: Session,
    a: Actor,
    department_id: str | None,
    academic_period_id: str | None,
    date_from: str | None,
    date_to: str | None,
    include_students: str | None,
) -> dict:
    """GET /reports/department-attendance (FR-14): per course offering and section of the department (from the
    offering read model's department), the closed sessions held, the average of the students' percentages and the
    students below the threshold (listed when asked). A `report:read-all` holder must name the department (400
    `department_required`); a department head's own department cannot be known yet (PRD Q9), so without
    `report:read-all` the report is refused with 403 `department_unknown` once the period is resolved."""
    if department_id is not None:
        _domain(require_id, department_id, "department_id")
    first, last = _date(date_from, "date_from"), _date(date_to, "date_to")
    _range(first, last)
    listed = _flag(include_students, "include_students_below_threshold")
    if department_id is None and a.can(k.REPORT_READ_ALL):
        raise invalid("department_required", "department_id is required for report:read-all holders", "department_id")
    period = _period(db, academic_period_id)
    if department_id is None or not a.can(k.REPORT_READ_ALL):
        raise _department_unknown()
    threshold = _threshold()
    offering_ids = ar.offering_ids_of_department(db, department_id, period)
    groups: dict[tuple[str, str], dict] = {}
    overall = rp.Tally()
    for record, session, cls in ar.attendance(
        db, academic_period_id=period, offering_ids=offering_ids, date_from=first, date_to=last
    ):
        group = groups.setdefault(
            (cls.course_offering_id, cls.section_id),
            {"instructor_id": cls.instructor_id, "sessions": set(), "students": defaultdict(list)},
        )
        group["sessions"].add(session.id)
        group["students"][record.student_id].append(record.status)
    offerings = repo.offering_refs(db, {o for o, _ in groups})
    sections = ar.section_refs_any(db, {s for _, s in groups})
    names = ar.student_names(db, {s for g in groups.values() for s in g["students"]}) if listed else {}
    items = []
    for (offering_id, section_id), group in groups.items():
        tallies = {student: rp.tally(found) for student, found in group["students"].items()}
        for t in tallies.values():
            overall = overall.plus(t)
        below = sorted(
            ((s, t) for s, t in tallies.items() if t.below(threshold)), key=lambda st: (st[1].percentage, st[0])
        )
        item: dict = {"course_offering_id": offering_id}
        ref = offerings.get(offering_id)
        if ref is not None and ref.course_code is not None:
            item["course_code"] = ref.course_code
        if ref is not None and ref.course_title is not None:
            item["course_title"] = ref.course_title
        item["section_id"] = section_id
        if section_id in sections:
            item["section_code"] = sections[section_id].code
        item.update(
            {
                "instructor_id": group["instructor_id"],
                "classes_held": len(group["sessions"]),
                "average_percentage": _mean([t.percentage for t in tallies.values() if t.percentage is not None]),
                "students_below_threshold": len(below),
            }
        )
        if listed:
            item["students"] = [
                {
                    "student_id": s,
                    **({"student_name": names[s]} if s in names else {}),
                    "percentage": _number(t.percentage),
                }
                for s, t in below
            ]
        items.append(item)
    items.sort(
        key=lambda i: (
            i.get("course_code") or "",
            i["course_offering_id"],
            i.get("section_code") or "",
            i["section_id"],
        )
    )
    return {
        "department_id": department_id,
        "academic_period_id": period,
        "date_from": iso(first),
        "date_to": iso(last),
        "threshold_percent": threshold,
        "overall_percentage": _number(overall.percentage),
        "items": items,
    }


# ---------------------------------------------------------------- exam eligibility


def eligibility(db: Session, a: Actor, body: object) -> dict:
    """POST /reports/attendance-eligibility (FR-18, owner decision C7): per student, the closed sessions of the
    offering's non-cancelled classes dated in the range for which the student was eligible (the snapshot taken at
    opening), without the excused ones, and how many were attended. No threshold is applied. Requested students never
    allocated to the offering's sections in the range, and with no record, are listed as unknown."""
    data = svc._object(body, "body", ("course_offering_id", "cutoff_date", "from_date", "student_ids"))
    for field in ("course_offering_id", "cutoff_date"):
        if field not in data:
            raise invalid("missing_field", f"{field} is required", field)
    offering_id = _domain(require_id, data["course_offering_id"], "course_offering_id")
    cutoff = svc._parse_date(data["cutoff_date"], "cutoff_date")
    first = None if data.get("from_date") is None else svc._parse_date(data["from_date"], "from_date")
    _range(first, cutoff, "cutoff_date")
    requested = None
    if data.get("student_ids") is not None:
        if not isinstance(data["student_ids"], list):
            raise invalid("invalid_body", "student_ids must be a list", "student_ids")
        if len(data["student_ids"]) > MAX_STUDENTS:
            raise invalid("too_many_students", f"student_ids lists at most {MAX_STUDENTS} students", "student_ids")
        requested = list(dict.fromkeys(_domain(require_id, s, "student_ids") for s in data["student_ids"]))
    if not repo.offering_refs(db, {offering_id}):
        raise not_found("unknown_course_offering", f"course offering {offering_id} is not known")
    statuses: dict[str, list[str]] = defaultdict(list)
    sections = ar.section_ids_of_offering(db, offering_id)
    for record, _, cls in ar.attendance(db, course_offering_id=offering_id, date_from=first, date_to=cutoff):
        statuses[record.student_id].append(record.status)
        sections.add(cls.section_id)
    allocated = ar.students_in_sections_between(db, sections, first, cutoff)
    known = allocated | set(statuses)
    population = sorted(known) if requested is None else [s for s in requested if s in known]
    items = []
    for student_id in population:
        t = rp.tally(statuses.get(student_id, []))
        items.append(
            {
                "student_id": student_id,
                "classes_counted": t.held,
                "attended": t.attended,
                "absent": t.absent,
                "excused": t.excused,
                "no_eligible_classes": rp.no_eligible_classes(t),
            }
        )
    return {
        "course_offering_id": offering_id,
        "from_date": iso(first),
        "cutoff_date": iso(cutoff),
        "generated_at": iso(_now()),
        "items": items,
        "unknown_student_ids": [] if requested is None else [s for s in requested if s not in known],
        "open_sessions_excluded": ar.open_sessions_of_offering(db, offering_id, first, cutoff),
    }
