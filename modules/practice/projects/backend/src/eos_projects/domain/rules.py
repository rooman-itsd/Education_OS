"""Domain rules of projects (docs/prd.md, "Main flows" and "Rules"). Pure functions and constants: no framework,
no database. The application layer calls these before it changes state."""

from __future__ import annotations

from datetime import date

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

PROJECT_STATUSES = ("proposed", "active", "submitted", "completed", "rejected", "cancelled")
MILESTONE_STATUSES = ("pending", "submitted", "accepted", "returned", "cancelled")
MEMBER_ROLES = ("lead", "member")

# A project in one of these is finished: nothing about it changes any more (PRD rule "nothing is deleted").
PROJECT_CLOSED = ("completed", "rejected", "cancelled")
# A project in one of these has a team that may still change.
TEAM_OPEN = ("proposed", "active")
# A milestone in one of these is the team's to submit (and is overdue once its due date has passed).
MILESTONE_OPEN = ("pending", "returned")

# Allowed transitions: action -> (from statuses, to status).
PROJECT_TRANSITIONS = {
    "approve": (("proposed",), "active"),
    "reject": (("proposed",), "rejected"),
    "submit": (("active",), "submitted"),
    "complete": (("submitted",), "completed"),
    "return": (("submitted",), "active"),
    "cancel": (("proposed", "active"), "cancelled"),
}
MILESTONE_TRANSITIONS = {
    "submit": (("pending", "returned"), "submitted"),
    "accept": (("submitted",), "accepted"),
    "return": (("submitted",), "returned"),
    "cancel": (("pending", "submitted", "returned"), "cancelled"),
}


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


# ---------------------------------------------------------------- projects and teams


def check_period(starts_on: date | None, ends_on: date | None) -> None:
    if starts_on is not None and ends_on is not None and ends_on < starts_on:
        raise RuleViolationError("invalid_dates", "ends_on must not be before starts_on")


def check_not_closed(status: str) -> None:
    if status in PROJECT_CLOSED:
        raise RuleViolationError("invalid_status", f"the project is {status}")


def check_team(member_ids: list[str], lead_id: str | None, guide_ids: list[str]) -> None:
    """A team has exactly one lead who is a member, and nobody is both team member and guide (PRD rules)."""
    if not lead_id or lead_id not in member_ids:
        raise RuleViolationError("no_lead", "the project needs a lead who is a team member")
    check_guides(guide_ids, member_ids)


def check_guides(guide_ids: list[str], member_ids: list[str]) -> None:
    if not guide_ids:
        raise RuleViolationError("guide_required", "the project needs at least one guide")
    both = sorted(set(guide_ids) & set(member_ids))
    if both:
        raise RuleViolationError("member_is_guide", f"{both[0]} is a team member and cannot be a guide")


def check_reason(reason: str | None, what: str) -> str:
    text = (reason or "").strip()
    if len(text) < 3:
        raise RuleViolationError("reason_required", f"a reason is required to {what}")
    return text


# ---------------------------------------------------------------- milestones, reviews and evaluation


def is_overdue(status: str, due_on: date, today: date) -> bool:
    """A milestone the team still has to submit is overdue from the day after its due date."""
    return status in MILESTONE_OPEN and due_on < today


def check_review(decision: str, comments: str | None) -> None:
    if decision == "returned" and not (comments or "").strip():
        raise RuleViolationError("comments_required", "comments are required to return a milestone")


def check_evaluation(decision: str, outcome: str | None) -> None:
    if decision == "completed" and not (outcome or "").strip():
        raise RuleViolationError("outcome_required", "an outcome is required to complete the project")


def progress(milestone_statuses: list[str]) -> tuple[int, int]:
    """(accepted, total) for the project's progress. Cancelled milestones do not count."""
    live = [s for s in milestone_statuses if s != "cancelled"]
    return sum(1 for s in live if s == "accepted"), len(live)


def not_accepted(milestones: list[tuple[str, str]]) -> list[str]:
    """Ids of milestones (id, status) the final submission goes in without: neither accepted nor cancelled."""
    return [mid for mid, status in milestones if status not in ("accepted", "cancelled")]


def days_between(earlier: date, later: date) -> int:
    return (later - earlier).days
