"""Domain rules of sports-nutrition-health (docs/prd.md). Pure functions over plain values: no framework, no database."""

from __future__ import annotations

from datetime import date, datetime, timedelta

CLOSED_PLAN = frozenset({"completed", "archived"})
CLOSED_APPOINTMENT = frozenset({"completed", "cancelled", "no_show"})
# What a scheduled appointment may become; a closed one keeps its status.
APPOINTMENT_MOVES = {"scheduled": frozenset({"scheduled", "completed", "cancelled", "no_show"})}


class RuleViolationError(Exception):
    """A request the rules refuse. The API answers 400 with {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def not_in_future(value: date, now: datetime, what: str) -> None:
    """A date may be one day ahead of today in UTC: it is already that day in timezones east of UTC (IST until 05:30)."""
    if value > (now + timedelta(days=1)).date():
        raise RuleViolationError("in_future", f"{what} cannot be in the future")


def not_before(later: date | None, earlier: date | None, what: str, than: str) -> None:
    if later is not None and earlier is not None and later < earlier:
        raise RuleViolationError("invalid_dates", f"{what} cannot be before {than}")


def check_plan_open(status: str) -> None:
    if status in CLOSED_PLAN:
        raise RuleViolationError("plan_closed", f"this plan is {status}; create a new plan instead")


def plan_after_review(outcome: str, next_review_on: date | None) -> dict:
    """What a review changes on its plan: ending it completes the plan and clears the review date; otherwise the next
    review date, when given, becomes the plan's review_due_on."""
    if outcome == "end":
        return {"status": "completed", "review_due_on": None}
    return {} if next_review_on is None else {"review_due_on": next_review_on}


def check_new_appointment(status: str) -> None:
    if status not in ("scheduled", "completed"):
        raise RuleViolationError(
            "invalid_status", "an appointment is created scheduled, or completed to log a past one"
        )


def check_appointment_change(current: str, changes: dict) -> None:
    """A closed appointment (completed, cancelled, no-show) only takes notes; a scheduled one may move to any status."""
    if current in CLOSED_APPOINTMENT:
        if set(changes) - {"notes"}:
            raise RuleViolationError("appointment_closed", f"this appointment is {current}; only notes can change")
        return
    if changes.get("status", current) not in APPOINTMENT_MOVES[current]:
        raise RuleViolationError("invalid_status", f"cannot move a {current} appointment to {changes['status']}")


def check_held(scheduled_at: datetime, now: datetime, status: str = "completed") -> None:
    """Completed and no-show both say something about a time that has passed."""
    if scheduled_at > now:
        what = "completed" if status == "completed" else "marked no-show"
        raise RuleViolationError("not_yet_held", f"an appointment cannot be {what} before its time")


def check_upcoming(scheduled_at: datetime, now: datetime) -> None:
    """A scheduled appointment is in the future; a past session is logged as completed instead."""
    if scheduled_at < now:
        raise RuleViolationError(
            "in_past", "a scheduled appointment must be in the future; log a past one as completed"
        )


def check_reviewable(status: str) -> None:
    """Only an active plan is reviewed: a draft has not started, a completed or archived one has ended."""
    check_plan_open(status)
    if status == "draft":
        raise RuleViolationError("plan_not_active", "activate the plan before reviewing it")
