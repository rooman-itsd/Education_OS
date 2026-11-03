"""Engagements: breakdown calls and preventive visits made to a vendor under a contract (PRD main flows 5 and 6).

open -> in_progress -> resolved -> closed, and open or in_progress -> cancelled. Whether the vendor kept to the
contract's response and resolution hours is worked out when read (within_terms)."""

from __future__ import annotations

from datetime import datetime, timedelta

from .errors import DomainRuleError

OPEN = "open"
IN_PROGRESS = "in_progress"
RESOLVED = "resolved"
CLOSED = "closed"
CANCELLED = "cancelled"
ENGAGEMENT_STATUSES = (OPEN, IN_PROGRESS, RESOLVED, CLOSED, CANCELLED)  # contract EngagementStatus
FINAL_STATUSES = (CLOSED, CANCELLED)

ENGAGEMENT_KINDS = ("breakdown_call", "preventive_visit")  # contract EngagementKind

# POST /engagements/{id}/status: the moves the contract allows, by target status.
MOVES = {
    IN_PROGRESS: (OPEN,),
    RESOLVED: (IN_PROGRESS,),
    CLOSED: (RESOLVED,),
    CANCELLED: (OPEN, IN_PROGRESS),
}
TARGET_STATUSES = tuple(MOVES)  # contract EngagementStatusInput.status, in its order


def move(current: str, target: str, *, resolution_note: str | None = None, note: str | None = None) -> str:
    """The new status, or 409 when the move is not allowed from `current`, or 422 when its note is missing."""
    if target not in MOVES:
        raise DomainRuleError("invalid_status", f"unknown status {target}", kind="invalid", field="status")
    if current not in MOVES[target]:
        raise DomainRuleError(
            "transition_not_allowed",
            f"an engagement cannot move from {current} to {target}",
            kind="conflict",
            field="status",
        )
    if target == RESOLVED and not (resolution_note or "").strip():
        raise DomainRuleError(
            "resolution_note_required", "resolving needs a resolution_note", kind="invalid", field="resolution_note"
        )
    if target == CANCELLED and not (note or "").strip():
        raise DomainRuleError("note_required", "cancelling needs a note", kind="invalid", field="note")
    return target


def check_editable(status: str) -> None:
    """PATCH /engagements/{id}: 409 when the engagement is closed or cancelled."""
    if status in FINAL_STATUSES:
        raise DomainRuleError("engagement_closed", f"a {status} engagement cannot be edited", kind="conflict")


def within_terms(
    *,
    response_hours: int | None,
    resolution_hours: int | None,
    reported_at: datetime,
    vendor_responded_at: datetime | None,
    resolved_at: datetime | None,
) -> bool | None:
    """Whether the vendor responded and resolved within the contract's hours, counted from reported_at.

    - None when the contract sets neither response_hours nor resolution_hours.
    - False as soon as a recorded response or resolution came too late.
    - True once every term the contract sets has been met.
    - Otherwise None: not yet measurable, because a term is set and its time is not recorded yet.

    Worked out from the recorded times only, never from the clock, so a reading never changes on its own."""
    if response_hours is None and resolution_hours is None:
        return None
    met: list[bool | None] = []  # one entry per term the contract sets; None while its time is not recorded
    for hours, at in ((response_hours, vendor_responded_at), (resolution_hours, resolved_at)):
        if hours is not None:
            met.append(None if at is None else at - reported_at <= timedelta(hours=hours))
    if any(m is False for m in met):
        return False
    if all(m is True for m in met):
        return True
    return None
