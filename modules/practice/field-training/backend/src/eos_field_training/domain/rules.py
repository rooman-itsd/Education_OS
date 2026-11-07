"""Domain rules of field-training (docs/prd.md, "Main flows" and "Rules"). Pure functions and constants: no framework,
no database. The application layer calls these before it changes state."""

from __future__ import annotations

from datetime import date, timedelta

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

OPENING_STATUSES = ("draft", "open", "closed", "cancelled")
PLACEMENT_STATUSES = ("requested", "assigned", "active", "completed", "rejected", "withdrawn")
LOG_STATUSES = ("submitted", "verified", "returned")
ASSESSMENT_STAGES = ("mid", "final")

# A placement in one of these takes a seat in its opening. A request does not: approving it takes the seat.
SEAT_HOLDING = ("assigned", "active", "completed")
# A placement in one of these blocks another placement of the same trainee over the same dates.
OVERLAP_BLOCKING = ("requested", "assigned", "active")
# A trainee holds at most one of these per opening; after a rejection or withdrawal they may apply again.
ONE_PER_OPENING = ("requested", "assigned", "active", "completed")
# Placements still to come or under way: what cancelling an opening withdraws, and what may still change.
OPEN_PLACEMENT = ("requested", "assigned", "active")

# Allowed transitions: action -> (from statuses, to status).
OPENING_TRANSITIONS = {
    "publish": (("draft",), "open"),
    "close": (("open",), "closed"),
    "cancel": (("draft", "open", "closed"), "cancelled"),
}
PLACEMENT_TRANSITIONS = {
    "approve": (("requested",), "assigned"),
    "reject": (("requested",), "rejected"),
    "start": (("assigned",), "active"),
    "complete": (("active",), "completed"),
    "withdraw": (("requested", "assigned", "active"), "withdrawn"),
}
LOG_TRANSITIONS = {
    "verify": (("submitted",), "verified"),
    "return": (("submitted",), "returned"),
    "edit": (("submitted", "returned"), "submitted"),
}

# Hours are stored as whole minutes so sums are exact; the contract's step of 0.25 hours is 15 minutes.
MINUTES_PER_HOUR = 60
HOUR_STEP_MINUTES = 15
MAX_MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
# A final assessment is due from this many days before the placement's end date (contract, GET /me/trainees).
FINAL_DUE_DAYS = 7
# GET /me/hours shows this many days by date, today included.
HOURS_WINDOW_DAYS = 14


class RuleViolationError(Exception):
    """A domain rule refused the change. `code` is stable; the API maps it to a status."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def transition(transitions: dict, action: str, current: str) -> str:
    """The status after `action`, or RuleViolationError when `current` does not allow it."""
    allowed_from, to = transitions[action]
    if current not in allowed_from:
        raise RuleViolationError("invalid_status", f"cannot {action} when status is {current}")
    return to


# ---------------------------------------------------------------- hours


def to_minutes(hours: float) -> int:
    """Hours in steps of 0.25 as whole minutes. Anything else is refused, never rounded."""
    minutes = hours * MINUTES_PER_HOUR
    if minutes < 0 or minutes != int(minutes) or int(minutes) % HOUR_STEP_MINUTES:
        raise RuleViolationError("invalid_hours", "hours go in steps of 0.25")
    return int(minutes)


def to_hours(minutes: int | None) -> float:
    return (minutes or 0) / MINUTES_PER_HOUR


def check_day_total(already: int, adding: int) -> None:
    """A trainee's entries for one date add up to at most 24 hours."""
    if already + adding > MAX_MINUTES_PER_DAY:
        left = max(MAX_MINUTES_PER_DAY - already, 0)
        raise RuleViolationError("day_over_24_hours", f"only {to_hours(left):g} more hours can be logged on that date")


def hours_short(verified: int, required: int) -> bool:
    return verified < required


# ---------------------------------------------------------------- periods


def check_period(start: date, end: date) -> None:
    if end < start:
        raise RuleViolationError("invalid_dates", "ends_on must not be before starts_on")


def check_within(start: date, end: date, outer_start: date, outer_end: date) -> None:
    """A placement's period falls inside its opening's period."""
    check_period(start, end)
    if start < outer_start or end > outer_end:
        raise RuleViolationError(
            "invalid_dates", f"the placement must fall inside the opening's period {outer_start} to {outer_end}"
        )


def periods_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def seats_left(seats: int, filled: int) -> int:
    return max(seats - filled, 0)


def check_seat(seats: int, filled: int) -> None:
    """Seats are never over-filled (PRD flow 3)."""
    if filled >= seats:
        raise RuleViolationError("no_seats", f"all {seats} seats of the opening are filled")


def check_seats_not_below_filled(seats: int, filled: int) -> None:
    if seats < filled:
        raise RuleViolationError("seats_below_filled", f"{filled} seats are already filled")


# ---------------------------------------------------------------- logbook


def log_window(starts_on: date, started_on: date | None, ends_on: date) -> tuple[date, date]:
    """Dates a log entry may carry: the placement's period, from the day it started when it was started early."""
    first = min(starts_on, started_on) if started_on else starts_on
    return first, ends_on


def check_log_date(on: date, starts_on: date, started_on: date | None, ends_on: date, today: date) -> None:
    first, last = log_window(starts_on, started_on, ends_on)
    if on < first or on > last:
        raise RuleViolationError("date_outside_placement", f"the date must fall between {first} and {last}")
    if on > today:
        raise RuleViolationError("date_in_future", "hours cannot be logged for a date that has not come yet")


# ---------------------------------------------------------------- completion


def completion_refusal(
    status: str, has_final: bool, verified: int, required: int, override: bool, reason: str | None
) -> tuple[str, str] | None:
    """Why a placement cannot be completed, as (Refusal code, message) from the contract, or None when it can."""
    if status != "active":
        return "not-active", f"only an active placement can be completed; this one is {status}"
    if not has_final:
        return "no-final-assessment", "record a final assessment before completing the placement"
    if hours_short(verified, required):
        if not override:
            return "hours-short", (
                f"{to_hours(verified):g} of {to_hours(required):g} required hours are verified; "
                "complete with override and a reason"
            )
        if len((reason or "").strip()) < 3:
            return "reason-required", "a reason is required to complete short of the required hours"
    return None


# ---------------------------------------------------------------- supervision


def final_assessment_due(ends_on: date, today: date, has_final: bool) -> bool:
    """Within FINAL_DUE_DAYS of the end date, or past it, with no final assessment recorded."""
    return not has_final and ends_on - timedelta(days=FINAL_DUE_DAYS) <= today


def urgency(final_due: bool, entries_awaiting: int, ends_on: date) -> tuple:
    """Sort key for GET /me/trainees: final assessments due first, nearest end date first, then most entries."""
    return (0 if final_due else 1, ends_on, -entries_awaiting)


def my_placement_rank(status: str, starts_on: date) -> tuple:
    """GET /me/placements: active first, then upcoming (assigned) soonest first, then requested, then past newest
    first."""
    order = {"active": 0, "assigned": 1, "requested": 2}
    rank = order.get(status, 3)
    return (rank, -starts_on.toordinal() if rank == 3 else starts_on.toordinal())
