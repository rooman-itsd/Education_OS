"""Rules of a grievance case (docs/prd.md "Tracks and committees", "Statuses", "Rules"). Pure Python: no framework, no
database, no clock; callers pass the time in.

Statuses:

    submitted -> acknowledged -> under_inquiry -> decided -> closed
    submitted -> not_admitted                                         (final)
    submitted | acknowledged | under_inquiry -> withdrawn             (final)
    decided -> appealed -> appeal_decided -> closed                   (student_grievance track only)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .errors import DomainRuleError

TRACKS = ("student_grievance", "ragging", "sexual_harassment")
COMMITTEE_KINDS = ("sgrc", "anti_ragging", "icc", "ombudsperson")
MEMBER_ROLES = ("chair", "member", "external_member")
STATUSES = (
    "submitted",
    "acknowledged",
    "under_inquiry",
    "decided",
    "appealed",
    "appeal_decided",
    "closed",
    "not_admitted",
    "withdrawn",
)
CLOSURES = ("decided", "withdrawn", "not_admitted")
PROCEEDING_KINDS = ("hearing", "statement", "note")
DECISION_OUTCOMES = ("upheld", "partly_upheld", "not_upheld")
APPEAL_OUTCOMES = ("upheld", "modified", "dismissed")
DAY_COUNTING = ("calendar", "working")

KIND_FOR_TRACK = {"student_grievance": "sgrc", "ragging": "anti_ragging", "sexual_harassment": "icc"}
TRACK_FOR_KIND = {kind: track for track, kind in KIND_FOR_TRACK.items()}

OPEN_STATUSES = ("submitted", "acknowledged", "under_inquiry", "decided", "appealed", "appeal_decided")
FINAL_STATUSES = ("closed", "not_admitted", "withdrawn")
WITHDRAWABLE = ("submitted", "acknowledged", "under_inquiry")
TRANSFERABLE = WITHDRAWABLE
PROCEEDING_STATUSES = ("acknowledged", "under_inquiry")
APPEALED_STATUSES = ("appealed", "appeal_decided")

# Moves a committee member makes through POST /grievances/{id}/status: (from, to).
STATUS_MOVES = {
    ("submitted", "acknowledged"),
    ("acknowledged", "under_inquiry"),
    ("submitted", "not_admitted"),
    ("decided", "closed"),
    ("appeal_decided", "closed"),
}

# Dates are accepted from 1900-01-01 to 2199-12-31 everywhere, as in the other governance modules.
MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2199, 12, 31)
# Upper bound of every "days" setting: keeps each date sum far from the end of the calendar.
MAX_DAYS = 3650


def conflict(code: str, message: str) -> DomainRuleError:
    return DomainRuleError(code, message, kind="conflict")


def invalid(code: str, message: str) -> DomainRuleError:
    return DomainRuleError(code, message, kind="invalid")


def is_open(status: str) -> bool:
    return status in OPEN_STATUSES


def check_move(status: str, target: str) -> None:
    if (status, target) not in STATUS_MOVES:
        raise conflict("invalid_status", f"a {status} case cannot move to {target}")


def committee_fits_track(kind: str, track: str) -> bool:
    return KIND_FOR_TRACK.get(track) == kind


def add_days(start: datetime, days: int, counting: str | None) -> datetime:
    """`start` plus `days` days. "working" skips Saturdays and Sundays (no holiday calendar); anything else counts
    calendar days."""
    if counting != "working":
        return start + timedelta(days=days)
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def due_at(
    status: str,
    filed_at: datetime,
    acknowledge_days: int | None,
    decide_days: int | None,
    counting: str | None,
) -> datetime | None:
    """When the case must next move, from the per-track settings; None when no setting applies.

    A submitted case is due `acknowledge_days` after filing; an acknowledged or under-inquiry case is due `decide_days`
    after filing. Later open statuses wait for the complainant's appeal or a close, which have no deadline of their own.
    """
    if status == "submitted" and acknowledge_days is not None:
        return add_days(filed_at, acknowledge_days, counting)
    if status in ("acknowledged", "under_inquiry") and decide_days is not None:
        return add_days(filed_at, decide_days, counting)
    return None


def is_overdue(status: str, due: datetime | None, now: datetime) -> bool:
    return is_open(status) and due is not None and now > due


def appeal_open(decided_at: datetime | None, window_days: int | None, counting: str | None, now: datetime) -> bool:
    """Inside the appeal window. Never while the window is not configured."""
    if decided_at is None or window_days is None:
        return False
    return now <= add_days(decided_at, window_days, counting)
