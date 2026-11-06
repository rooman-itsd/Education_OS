"""Problems, root-cause analyses and corrective actions (PRD "Main flows" 5 to 9, "Statuses" and "Rules").

Problem: open -> investigating -> known_error (optional, needs a workaround) -> resolved (needs a published RCA)
-> closed, and investigating -> resolved. RCA: draft -> published, then read-only. Corrective action: open -> done
or cancelled; overdue is worked out when read, never stored."""

from __future__ import annotations

from datetime import date

from .errors import DomainRuleError

OPEN = "open"
INVESTIGATING = "investigating"
KNOWN_ERROR = "known_error"
RESOLVED = "resolved"
CLOSED = "closed"
PROBLEM_STATUSES = (OPEN, INVESTIGATING, KNOWN_ERROR, RESOLVED, CLOSED)  # contract ProblemStatus

# POST /problems/{id}/status: the moves the contract allows, by target status.
MOVES = {
    INVESTIGATING: (OPEN,),
    KNOWN_ERROR: (INVESTIGATING,),
    RESOLVED: (INVESTIGATING, KNOWN_ERROR),
    CLOSED: (RESOLVED,),
}
TARGET_STATUSES = tuple(MOVES)  # contract ProblemStatusInput.status, in its order

DRAFT = "draft"
PUBLISHED = "published"
RCA_STATUSES = (DRAFT, PUBLISHED)  # contract RcaStatus

ACTION_OPEN = "open"
ACTION_DONE = "done"
ACTION_CANCELLED = "cancelled"
ACTION_STATUSES = (ACTION_OPEN, ACTION_DONE, ACTION_CANCELLED)  # contract ActionStatus
ACTION_TARGETS = (ACTION_DONE, ACTION_CANCELLED)  # contract ActionUpdateInput.status


def move(current: str, target: str, *, workaround: str | None, rca_status: str | None) -> str:
    """The new problem status, or 409 when the move is not allowed or the RCA is not published, or 422 when a move to
    known_error has no workaround (sent now or already recorded)."""
    if target not in MOVES:
        raise DomainRuleError("invalid_status", f"unknown status {target}", kind="invalid", field="status")
    if current not in MOVES[target]:
        raise DomainRuleError(
            "transition_not_allowed",
            f"a problem cannot move from {current} to {target}",
            kind="conflict",
            field="status",
        )
    if target == KNOWN_ERROR and not (workaround or "").strip():
        raise DomainRuleError(
            "workaround_required", "a known error needs a workaround", kind="invalid", field="workaround"
        )
    if target == RESOLVED and rca_status != PUBLISHED:
        raise DomainRuleError(
            "rca_not_published", "resolving a problem needs a published RCA", kind="conflict", field="status"
        )
    return target


def check_editable(status: str) -> None:
    """PATCH /problems/{id}: 409 when the problem is closed."""
    if status == CLOSED:
        raise DomainRuleError("problem_closed", "a closed problem cannot be changed", kind="conflict")


def check_workaround_kept(status: str, workaround: str | None) -> None:
    """A known error keeps its workaround: PATCH cannot blank it (422)."""
    if status == KNOWN_ERROR and not (workaround or "").strip():
        raise DomainRuleError(
            "workaround_required", "a known error needs a workaround", kind="invalid", field="workaround"
        )


def check_can_link(status: str) -> None:
    """A closed problem takes no new incidents (PATCH /incidents/{id} with problem_id, 409)."""
    if status == CLOSED:
        raise DomainRuleError(
            "problem_closed", "a closed problem takes no new incidents", kind="conflict", field="problem_id"
        )


def check_can_add_action(status: str) -> None:
    """POST /problems/{id}/actions: 409 when the problem is closed."""
    if status == CLOSED:
        raise DomainRuleError("problem_closed", "a closed problem takes no new corrective actions", kind="conflict")


def check_rca_editable(status: str) -> None:
    """PUT /problems/{id}/rca: a published RCA is read-only (409)."""
    if status == PUBLISHED:
        raise DomainRuleError("rca_published", "a published RCA cannot be changed", kind="conflict")


def publish_rca(status: str) -> str:
    """POST /problems/{id}/rca/publish: draft -> published (409 when already published)."""
    if status != DRAFT:
        raise DomainRuleError("rca_published", "the RCA is already published", kind="conflict")
    return PUBLISHED


def check_action_editable(status: str) -> None:
    """PATCH /problems/{id}/actions/{action_id}: 409 when the action is already done or cancelled."""
    if status != ACTION_OPEN:
        raise DomainRuleError("action_closed", f"the action is already {status}", kind="conflict")


def check_due_date(due: date, today: date) -> None:
    """A new or changed due date is today or later (422)."""
    if due < today:
        raise DomainRuleError("due_date_in_past", "due_date cannot be in the past", kind="invalid", field="due_date")


def is_overdue(status: str, due: date, today: date) -> bool:
    """Open and past its due date. On the due date itself an action is not overdue yet."""
    return status == ACTION_OPEN and due < today
