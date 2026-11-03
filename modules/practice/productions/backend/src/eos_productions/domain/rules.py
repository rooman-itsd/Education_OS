"""Rules of productions, with no database and no HTTP in sight (docs/prd.md section 4).

A production moves planned -> in_preparation -> scheduled -> completed, and may be cancelled from any of
those. Dates are only required once it is scheduled, because an academy puts a show on the calendar long
before it knows the hall. Everything here is pure, so the tests in backend/tests/test_domain.py pin the
rules without a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

KINDS = ("performance", "exhibition", "recital", "screening", "hackathon", "competition", "conference", "other")

PLANNED = "planned"
IN_PREPARATION = "in_preparation"
SCHEDULED = "scheduled"
COMPLETED = "completed"
CANCELLED = "cancelled"
STATUSES = (PLANNED, IN_PREPARATION, SCHEDULED, COMPLETED, CANCELLED)

#: A production nobody has finished with: it still appears on dashboards and may still be changed.
OPEN_STATUSES = (PLANNED, IN_PREPARATION, SCHEDULED)
#: What the in-preparation widget counts as "being got ready".
PREPARING_STATUSES = (PLANNED, IN_PREPARATION)
#: What the calendar and upcoming widgets show.
CALENDAR_STATUSES = (SCHEDULED,)

ROLE_KINDS = ("cast", "crew", "mentor")
INVITED = "invited"
CONFIRMED = "confirmed"
DECLINED = "declined"
WITHDRAWN = "withdrawn"
ROLE_STATUSES = (INVITED, CONFIRMED, DECLINED, WITHDRAWN)
#: An assignment that still ties a person to the production.
LIVE_ROLE_STATUSES = (INVITED, CONFIRMED)

TASK_OPEN = "open"
TASK_DONE = "done"

#: Which status each action may be taken from. Nothing changes a completed or cancelled production.
ALLOWED_FROM: dict[str, tuple[str, ...]] = {
    "edit": OPEN_STATUSES,
    "start_preparation": (PLANNED,),
    "schedule": (PLANNED, IN_PREPARATION, SCHEDULED),
    "complete": (SCHEDULED,),
    "cancel": OPEN_STATUSES,
    "assign_role": OPEN_STATUSES,
    "add_task": OPEN_STATUSES,
    "complete_task": OPEN_STATUSES,
}


class RuleViolationError(Exception):
    """A refusal that comes from the rules rather than from permissions or a missing row."""

    def __init__(self, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


@dataclass(frozen=True)
class ProductionRules:
    """Organisation-wide settings (config/env.example), read by infrastructure/config.py."""

    calendar_window_days: int = 60
    min_preparation_days: int = 7
    max_run_hours: int = 72
    default_call_minutes: int = 60


def check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise RuleViolationError("invalid_kind", f"kind must be one of {', '.join(KINDS)}")


def check_role_kind(kind: str) -> None:
    if kind not in ROLE_KINDS:
        raise RuleViolationError("invalid_role_kind", f"kind must be one of {', '.join(ROLE_KINDS)}")


def check_action(action: str, status: str) -> None:
    """Refuse an action the production's status does not allow, naming the status the caller saw."""
    allowed = ALLOWED_FROM[action]
    if status not in allowed:
        raise RuleViolationError(
            "wrong_status",
            f"a {status.replace('_', ' ')} production cannot be {_past(action)}",
            status=status,
        )


def _past(action: str) -> str:
    return {
        "edit": "edited",
        "start_preparation": "put into preparation",
        "schedule": "scheduled",
        "complete": "completed",
        "cancel": "cancelled",
        "assign_role": "cast",
        "add_task": "given tasks",
        "complete_task": "have tasks completed",
    }[action]


def check_schedule(
    starts_at: datetime,
    ends_at: datetime,
    call_time: datetime | None,
    rules: ProductionRules,
) -> None:
    """Dates a production can actually be run with. Nothing here looks at `now`: an academy records a
    performance that already happened, and moving a show earlier is a decision, not an error."""
    if ends_at <= starts_at:
        raise RuleViolationError("invalid_dates", "the production must end after it starts")
    if ends_at - starts_at > timedelta(hours=rules.max_run_hours):
        raise RuleViolationError(
            "run_too_long",
            f"a production may not run longer than {rules.max_run_hours} hours; check the dates",
            limit_hours=rules.max_run_hours,
        )
    if call_time is not None and call_time > starts_at:
        raise RuleViolationError("invalid_call_time", "the call time must not be after the start")


def default_call_time(starts_at: datetime, rules: ProductionRules) -> datetime:
    return starts_at - timedelta(minutes=rules.default_call_minutes)


def preparation_is_short(starts_at: datetime, now: datetime, rules: ProductionRules) -> bool:
    """True when a production is scheduled closer than the organisation's preparation window. The caller
    passes this back as a warning: it never refuses the schedule (PRD rule 7)."""
    return starts_at - now < timedelta(days=rules.min_preparation_days)


def check_response(role_status: str, production_status: str) -> None:
    """Accepting or declining is only possible while the offer is open and the production is alive."""
    if role_status != INVITED:
        raise RuleViolationError(
            "already_answered",
            f"this part was already {role_status}",
            status=role_status,
        )
    if production_status not in OPEN_STATUSES:
        raise RuleViolationError(
            "wrong_status",
            f"the production is {production_status.replace('_', ' ')}",
            status=production_status,
        )


def check_withdrawal(role_status: str) -> None:
    if role_status not in LIVE_ROLE_STATUSES:
        raise RuleViolationError("already_answered", f"this part is already {role_status}", status=role_status)


def is_overdue(due_at: datetime | None, now: datetime) -> bool:
    return due_at is not None and due_at < now
