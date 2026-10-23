"""Ticket statuses and the moves between them (contract `TicketStatus`, `Priority`, `HoldReason`; PRD main flows
4 to 8 and "Ticket states").

Each function takes the ticket's current status and returns the status after the operation, or raises
DomainRuleError. Not covered here: who may perform an operation and queue membership (permissions), assignment,
ticket numbering, the reopen and auto-close windows, and how the ticket's own time and count fields change. The
contract and PRD do not settle these fully, so they are left to later layers."""

from __future__ import annotations

from .errors import DomainRuleError

NEW = "new"
IN_PROGRESS = "in_progress"
ON_HOLD = "on_hold"
RESOLVED = "resolved"
CLOSED = "closed"
CANCELLED = "cancelled"
TICKET_STATUSES = (NEW, IN_PROGRESS, ON_HOLD, RESOLVED, CLOSED, CANCELLED)  # contract TicketStatus
# Open tickets: "new, in_progress, on_hold" (GET /stats/open-by-priority, Queue.open_count).
OPEN_STATUSES = (NEW, IN_PROGRESS, ON_HOLD)
# helpdesk.ticket.closed and helpdesk.ticket.cancelled are "Final" (events.yaml).
FINAL_STATUSES = (CLOSED, CANCELLED)

LOW, MEDIUM, HIGH, URGENT = "low", "medium", "high", "urgent"
PRIORITIES = (LOW, MEDIUM, HIGH, URGENT)  # contract Priority
# OpenByPriority.rows: "One row per priority, urgent first".
PRIORITIES_URGENT_FIRST = (URGENT, HIGH, MEDIUM, LOW)

WAITING_REQUESTER = "waiting_requester"
WAITING_THIRD_PARTY = "waiting_third_party"
WAITING_INTERNAL = "waiting_internal"
HOLD_REASONS = (WAITING_REQUESTER, WAITING_THIRD_PARTY, WAITING_INTERNAL)  # contract HoldReason


def require_status(status: object) -> str:
    """The value is a contract TicketStatus."""
    if not isinstance(status, str) or status not in TICKET_STATUSES:
        raise DomainRuleError("invalid_status", "status must be a TicketStatus", kind="invalid", field="status")
    return status


def _move(status: object, allowed_from: tuple[str, ...], to: str, operation: str) -> str:
    current = require_status(status)
    if current not in allowed_from:
        message = f"a {current} ticket cannot be {operation}"
        raise DomainRuleError("transition_not_allowed", message, kind="conflict", field="status")
    return to


def start_work(status: object) -> str:
    """POST /tickets/{id}/status with status in_progress: "new or on_hold → in_progress"; otherwise 409."""
    return _move(status, (NEW, ON_HOLD), IN_PROGRESS, "started")


def put_on_hold(status: object, hold_reason: object) -> str:
    """POST /tickets/{id}/status with status on_hold: "in_progress → on_hold"; otherwise 409. StatusInput:
    hold_reason is "Required when status is on_hold" and is a HoldReason."""
    if hold_reason is None:
        raise DomainRuleError("hold_reason_required", "a hold reason is required", kind="invalid", field="hold_reason")
    if hold_reason not in HOLD_REASONS:
        message = "hold_reason must be a HoldReason"
        raise DomainRuleError("invalid_hold_reason", message, kind="invalid", field="hold_reason")
    return _move(status, (IN_PROGRESS,), ON_HOLD, "put on hold")


def resolve(status: object) -> str:
    """POST /tickets/{id}/resolve: "new, in_progress or on_hold → resolved"; 409 when "Already resolved, closed or
    cancelled"."""
    return _move(status, OPEN_STATUSES, RESOLVED, "resolved")


def close(status: object) -> str:
    """resolved → closed, both when the requester confirms (POST /me/tickets/{id}/confirm, 409 "Not resolved") and
    for the daily auto-close (PRD main flow 7). Whether a ticket is old enough to auto-close is not decided here."""
    return _move(status, (RESOLVED,), CLOSED, "closed")


def reopen(status: object) -> str:
    """POST /me/tickets/{id}/reopen: "resolved → in_progress"; 409 when "Not resolved". The reopen window
    (HELPDESK_REOPEN_WINDOW_DAYS) is checked separately, not here."""
    return _move(status, (RESOLVED,), IN_PROGRESS, "reopened")


def withdraw(status: object) -> str:
    """POST /me/tickets/{id}/withdraw: "before it is resolved"; 409 when "Already resolved, closed or cancelled"."""
    return _move(status, OPEN_STATUSES, CANCELLED, "withdrawn")


def cancel(status: object, *, ticket_id: str, duplicate_of: str | None = None) -> str:
    """POST /tickets/{id}/cancel: 409 when "Already resolved, closed or cancelled, or duplicate_of is this ticket".
    CancelInput describes duplicate_of as "Another open ticket", but the contract names no error for one that is
    not open or does not exist, so only the "is this ticket" case is checked here."""
    if duplicate_of is not None and duplicate_of == ticket_id:
        message = "a ticket cannot be a duplicate of itself"
        raise DomainRuleError("duplicate_of_itself", message, kind="conflict", field="duplicate_of")
    return _move(status, OPEN_STATUSES, CANCELLED, "cancelled")


def ensure_can_comment(status: object) -> None:
    """POST /tickets/{id}/comments and POST /me/tickets/{id}/comments: 409 when "Ticket is closed or cancelled"."""
    current = require_status(status)
    if current in FINAL_STATUSES:
        message = f"a {current} ticket takes no more replies"
        raise DomainRuleError("ticket_final", message, kind="conflict", field="status")


def status_after_agent_public_reply(status: object) -> str:
    """POST /tickets/{id}/comments with visibility public: "A public reply on a new ticket also moves it to
    in_progress". No other status changes. An internal note changes no status; use ensure_can_comment."""
    current = require_status(status)
    ensure_can_comment(current)
    return IN_PROGRESS if current == NEW else current


def status_after_requester_reply(status: object, hold_reason: object) -> str:
    """POST /me/tickets/{id}/comments: "A reply to a ticket on hold waiting on the requester moves it back to
    in_progress". No other status changes."""
    current = require_status(status)
    ensure_can_comment(current)
    if current == ON_HOLD and hold_reason == WAITING_REQUESTER:
        return IN_PROGRESS
    return current


def ensure_can_reclassify(status: object) -> None:
    """PATCH /tickets/{id}: 409 when "Ticket is resolved, closed or cancelled"."""
    current = require_status(status)
    if current not in OPEN_STATUSES:
        message = f"a {current} ticket cannot be changed"
        raise DomainRuleError("transition_not_allowed", message, kind="conflict", field="status")
