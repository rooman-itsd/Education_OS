"""Attendance sessions and records (contracts `AttendanceSession`, `AttendanceRecord`; PRD 5.3, 5.4, FR-7 to FR-11).

Who may act is decided by the caller from the permission keys (own class, department, organisation) and handed in as
facts; this module holds the rules that do not depend on who asks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from .classes import CANCELLED, SCHEDULED, ScheduledClass
from .errors import DomainRuleError
from .values import require_choice, require_id, require_instant, require_text

PRESENT, ABSENT, LATE, EXCUSED = "present", "absent", "late", "excused"
ATTENDANCE_STATUSES = (PRESENT, ABSENT, LATE, EXCUSED)  # contract AttendanceStatus
ATTENDED = (PRESENT, LATE)  # FR-13: what counts as attended
OPEN, CLOSED = "open", "closed"
SESSION_STATUSES = (OPEN, CLOSED)  # contract AttendanceSessionStatus

REMARK_MAX = 500
REASON_MAX = 500


@dataclass(frozen=True)
class Policy:
    """The organisation-wide settings of config/env.example (open question Q5: they may become per-organisation)."""

    marking_opens_before_minutes: int = 15
    marking_window_hours: int = 24
    correction_window_days: int = 7
    shortage_threshold_percent: int = 75

    def __post_init__(self) -> None:
        for field in ("marking_opens_before_minutes", "marking_window_hours", "correction_window_days"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DomainRuleError("invalid_policy", f"{field} must be 0 or more", kind="invalid", field=field)
        threshold = self.shortage_threshold_percent
        if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 100:
            raise DomainRuleError(
                "invalid_policy",
                "shortage_threshold_percent must be between 0 and 100",
                kind="invalid",
                field="shortage_threshold_percent",
            )


@dataclass(frozen=True)
class MarkingWindow:
    opens_at: datetime
    closes_at: datetime  # the marking deadline: the class's end plus the marking window

    def contains(self, moment: datetime) -> bool:
        return self.opens_at <= moment <= self.closes_at


def marking_window(cls: ScheduledClass, policy: Policy) -> MarkingWindow:
    """FR-7: from `starts_at` minus the opening lead to `ends_at` plus the marking window."""
    return MarkingWindow(
        opens_at=cls.starts_at - timedelta(minutes=policy.marking_opens_before_minutes),
        closes_at=cls.ends_at + timedelta(hours=policy.marking_window_hours),
    )


@dataclass(frozen=True)
class Session:
    id: str
    scheduled_class_id: str
    opened_at: datetime
    opened_by: str
    marking_deadline: datetime
    status: str = OPEN
    closed_at: datetime | None = None
    closed_by: str | None = None  # None with a closed_at: the system closed it at the deadline

    def __post_init__(self) -> None:
        require_id(self.id, "id")
        require_id(self.scheduled_class_id, "scheduled_class_id")
        require_choice(self.status, "status", SESSION_STATUSES)
        require_instant(self.opened_at, "opened_at")
        if (self.status == CLOSED) != (self.closed_at is not None):
            raise DomainRuleError(
                "invalid_session", "a session has closed_at if and only if it is closed", kind="invalid"
            )


def ensure_can_open(cls: ScheduledClass, existing: Session | None, now: datetime, policy: Policy) -> Session | None:
    """FR-7, FR-8: whether an attendance session may be opened for the class now.

    Returns the session already open for the class (opening twice returns it, whatever the time), or None when a new
    one may be created. 409 when the class is not scheduled, its session is closed, or now is outside the marking
    window. Whether the caller may open it (own class or override) is the caller's check."""
    now = require_instant(now, "now")
    if existing is not None and existing.status == OPEN:
        return existing
    if existing is not None:  # closing completes the class, so a closed session is reported before the class status
        raise DomainRuleError("session_closed", "the attendance session is already closed", kind="conflict")
    if cls.status != SCHEDULED:
        if cls.status == CANCELLED:
            raise DomainRuleError("class_cancelled", "the class is cancelled", kind="conflict")
        raise DomainRuleError("class_completed", "the class is completed", kind="conflict")
    window = marking_window(cls, policy)
    if not window.contains(now):
        raise DomainRuleError(
            "outside_marking_window",
            "attendance can only be opened from "
            f"{policy.marking_opens_before_minutes} minutes before the class until {policy.marking_window_hours} "
            "hours after it ends",
            kind="conflict",
            details={"opens_at": window.opens_at.isoformat(), "closes_at": window.closes_at.isoformat()},
        )
    return None


def ensure_can_mark(session: Session, now: datetime) -> None:
    """FR-9: records are written while the session is open and before its deadline; a closed one takes corrections.
    A session past its deadline is closed by the system, so until it is, marking it is refused the same way."""
    if session.status != OPEN:
        raise DomainRuleError("session_closed", "the session is closed; use the correction endpoint", kind="conflict")
    if require_instant(now, "now") > session.marking_deadline:
        raise DomainRuleError(
            "marking_window_ended",
            "the marking window has ended; the session will be closed",
            kind="conflict",
            details={"marking_deadline": session.marking_deadline.isoformat()},
        )


def is_due_for_auto_close(session: Session, now: datetime) -> bool:
    """FR-11: a session still open when the marking window ends is closed by the system."""
    return session.status == OPEN and require_instant(now, "now") > session.marking_deadline


@dataclass(frozen=True)
class Mark:
    student_id: str
    status: str
    remark: str | None = None


def parse_marks(items: object) -> list[Mark]:
    """The `records` of a markAttendance request: at least one, each with a student id and a status, no student twice
    (one submission, one value per student)."""
    if not isinstance(items, list) or not items:
        raise DomainRuleError("no_records", "records must list at least one student", kind="invalid", field="records")
    marks: list[Mark] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise DomainRuleError("invalid_record", "each record must be an object", kind="invalid", field="records")
        student_id = require_id(item.get("student_id"), "student_id")
        if student_id in seen:
            raise DomainRuleError(
                "duplicate_student",
                f"student {student_id} is listed twice",
                kind="invalid",
                field="records",
                details={"student_id": student_id},
            )
        seen.add(student_id)
        marks.append(
            Mark(
                student_id=student_id,
                status=require_choice(item.get("status"), "status", ATTENDANCE_STATUSES),
                remark=_remark(item.get("remark")),
            )
        )
    return marks


def _remark(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainRuleError("invalid_text", "remark must be a string", kind="invalid", field="remark")
    text = value.strip()
    if len(text) > REMARK_MAX:
        raise DomainRuleError(
            "text_too_long", f"remark must be at most {REMARK_MAX} characters", kind="invalid", field="remark"
        )
    return text or None


def ensure_eligible(marks: Iterable[Mark], eligible_student_ids: Iterable[str]) -> None:
    """FR-9: only eligible students can be marked (422 with the ones that are not)."""
    eligible = set(eligible_student_ids)
    refused = sorted(m.student_id for m in marks if m.student_id not in eligible)
    if refused:
        raise DomainRuleError(
            "student_not_eligible",
            f"{len(refused)} student(s) are not eligible for this class",
            kind="unprocessable",
            field="records",
            details={"student_ids": refused},
        )


def counts(eligible_student_ids: Iterable[str], statuses: Mapping[str, str]) -> dict[str, int]:
    """The contract's `AttendanceCounts`: eligible students, those not yet marked, and one count per status.
    `statuses` maps a student id to the recorded status; students outside the eligible set are not counted."""
    eligible = list(dict.fromkeys(eligible_student_ids))
    tally = Counter(statuses[s] for s in eligible if s in statuses)
    result = {
        "eligible": len(eligible),
        "unmarked": sum(1 for s in eligible if s not in statuses),
    }
    result.update({status: tally.get(status, 0) for status in ATTENDANCE_STATUSES})
    return result


def plan_close(
    session: Session,
    eligible_student_ids: Iterable[str],
    statuses: Mapping[str, str],
    *,
    now: datetime,
    closed_by: str | None,
) -> tuple[Session, list[str]]:
    """FR-11: close an open session. Returns the closed session and the ids of the eligible students who were never
    marked and so become `absent`. `closed_by` is None when the system closes it at the deadline."""
    if session.status == CLOSED:
        raise DomainRuleError("session_closed", "the attendance session is already closed", kind="conflict")
    if closed_by is not None:
        require_id(closed_by, "closed_by")
    closed_at = require_instant(now, "now")
    unmarked = [s for s in dict.fromkeys(eligible_student_ids) if s not in statuses]
    closed = Session(
        id=session.id,
        scheduled_class_id=session.scheduled_class_id,
        opened_at=session.opened_at,
        opened_by=session.opened_by,
        marking_deadline=session.marking_deadline,
        status=CLOSED,
        closed_at=closed_at,
        closed_by=closed_by,
    )
    return closed, unmarked


# Who is correcting, as the caller establishes it from the keys the caller holds (FR-10).
INSTRUCTOR, DEPARTMENT, ORGANISATION = "instructor", "department", "organisation"
CORRECTION_SCOPES = (INSTRUCTOR, DEPARTMENT, ORGANISATION)


@dataclass(frozen=True)
class Correction:
    from_status: str
    to_status: str
    reason: str
    remark: str | None


def plan_correction(
    session: Session,
    from_status: str,
    to_status: object,
    reason: object,
    remark: object,
    *,
    scope: str,
    now: datetime,
    policy: Policy,
) -> Correction:
    """FR-10: a record of a closed session changes only through a correction with a reason.

    409 while the session is still open (mark instead), and, for the class's instructor (`scope` "instructor"), once
    the correction window since the session closed has passed. A department or organisation scope has no window."""
    require_choice(scope, "scope", CORRECTION_SCOPES)
    new_status = require_choice(to_status, "status", ATTENDANCE_STATUSES)
    text = require_text(reason, "reason", max_length=REASON_MAX)
    if session.status != CLOSED or session.closed_at is None:
        raise DomainRuleError("session_open", "the session is still open; mark attendance instead", kind="conflict")
    if scope == INSTRUCTOR and require_instant(now, "now") > session.closed_at + timedelta(
        days=policy.correction_window_days
    ):
        raise DomainRuleError(
            "correction_window_passed",
            f"records can be corrected for {policy.correction_window_days} day(s) after the session closes",
            kind="conflict",
        )
    if new_status == from_status:
        raise DomainRuleError(
            "status_unchanged", f"the record is already {from_status}", kind="invalid", field="status"
        )
    return Correction(from_status=from_status, to_status=new_status, reason=text, remark=_remark(remark))
