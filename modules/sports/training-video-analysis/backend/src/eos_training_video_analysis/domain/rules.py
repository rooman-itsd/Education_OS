"""Domain rules of training-video-analysis (docs/prd.md). Pure functions over plain values: no framework, no database."""

from __future__ import annotations

from datetime import date, datetime

# Plan status moves (contracts/openapi.yaml TrainingPlan.status). An archived plan is read-only.
PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"active", "archived"}),
    "active": frozenset({"completed", "archived"}),
    "completed": frozenset({"archived"}),
    "archived": frozenset(),
}
# A plan in one of these takes no new sessions.
PLAN_CLOSED = frozenset({"completed", "archived"})

# Session status moves (TrainingSession.status). Completed and cancelled are final.
SESSION_TRANSITIONS: dict[str, frozenset[str]] = {
    "scheduled": frozenset({"in_progress", "completed", "cancelled"}),
    "in_progress": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}
SESSION_CLOSED = frozenset({"completed", "cancelled"})
# Fields of a closed session that may still change: what happened is recorded after the session ends.
SESSION_EDITABLE_WHEN_CLOSED = frozenset({"notes", "attendee_ids", "drill_ids", "actual_duration_minutes"})


class RuleViolationError(Exception):
    """A request the rules refuse. The API answers 400 with {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_plan_period(start: date, end: date) -> None:
    if end < start:
        raise RuleViolationError("invalid_period", "end_date must not be before start_date")


def check_plan_transition(current: str, new: str) -> None:
    if new != current and new not in PLAN_TRANSITIONS[current]:
        raise RuleViolationError("invalid_transition", f"a {current} plan cannot become {new}")


def check_plan_editable(status: str) -> None:
    if status == "archived":
        raise RuleViolationError("plan_archived", "an archived plan cannot be changed")


def check_plan_open(status: str) -> None:
    if status in PLAN_CLOSED:
        raise RuleViolationError("plan_closed", f"a {status} plan takes no new sessions")


def check_session_window(start: datetime, end: datetime) -> None:
    if end <= start:
        raise RuleViolationError("invalid_period", "scheduled_end must be after scheduled_start")


def check_session_in_plan(local_start: date, plan_start: date, plan_end: date) -> None:
    """A session falls on a day of its plan, by the institution's local date."""
    if not plan_start <= local_start <= plan_end:
        raise RuleViolationError(
            "outside_plan", f"the session must start between the plan's {plan_start} and {plan_end}"
        )


def check_session_transition(current: str, new: str) -> None:
    if new != current and new not in SESSION_TRANSITIONS[current]:
        raise RuleViolationError("invalid_transition", f"a {current} session cannot become {new}")


def check_session_change(status: str, fields: set[str]) -> None:
    """A completed or cancelled session keeps its schedule; only the record of what happened may change."""
    if status in SESSION_CLOSED:
        locked = sorted(fields - SESSION_EDITABLE_WHEN_CLOSED)
        if locked:
            raise RuleViolationError("session_closed", f"a {status} session cannot change {', '.join(locked)}")


def check_completion(now: datetime, scheduled_start: datetime) -> None:
    if now < scheduled_start:
        raise RuleViolationError("not_started", "a session cannot be completed before it starts")


def check_duration_allowed(status: str) -> None:
    if status != "completed":
        raise RuleViolationError("not_completed", "actual_duration_minutes is recorded once the session is completed")


def completed_duration(actual_minutes: int | None, start: datetime, end: datetime) -> int:
    """The recorded duration, or the scheduled length when none was recorded."""
    if actual_minutes is not None:
        return actual_minutes
    return int((end - start).total_seconds() // 60)


def not_in_future(value: datetime, now: datetime, what: str) -> None:
    if value > now:
        raise RuleViolationError("in_future", f"{what} cannot be in the future")


def check_segment(start: float, end: float, video_duration: float) -> None:
    """A drill tag covers part of the video: 0 <= start < end <= duration."""
    if start < 0:
        raise RuleViolationError("invalid_timestamp", "start_timestamp cannot be negative")
    if end <= start:
        raise RuleViolationError("invalid_timestamp", "end_timestamp must be after start_timestamp")
    if end > video_duration:
        raise RuleViolationError("outside_video", "the segment ends after the video does")


def check_annotation_time(start: float, end: float | None, video_duration: float) -> None:
    """An annotation points at a moment of the video, or a span when it has an end."""
    if start < 0:
        raise RuleViolationError("invalid_timestamp", "start_timestamp cannot be negative")
    if start > video_duration:
        raise RuleViolationError("outside_video", "start_timestamp is after the end of the video")
    if end is not None:
        if end < start:
            raise RuleViolationError("invalid_timestamp", "end_timestamp must not be before start_timestamp")
        if end > video_duration:
            raise RuleViolationError("outside_video", "end_timestamp is after the end of the video")


def unique(values: list[str] | None) -> list[str]:
    """Ids once each, in the order first given."""
    return list(dict.fromkeys(values or []))
