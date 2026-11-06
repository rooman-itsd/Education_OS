"""Incidents (PRD "Main flows" 1 to 4, "Statuses" and "Rules").

open -> investigating; investigating <-> mitigated; investigating or mitigated -> resolved (needs a resolution
summary); resolved -> closed; resolved -> investigating (reopen, needs a note); open or investigating -> cancelled
(needs a note)."""

from __future__ import annotations

from .errors import DomainRuleError

OPEN = "open"
INVESTIGATING = "investigating"
MITIGATED = "mitigated"
RESOLVED = "resolved"
CLOSED = "closed"
CANCELLED = "cancelled"
INCIDENT_STATUSES = (OPEN, INVESTIGATING, MITIGATED, RESOLVED, CLOSED, CANCELLED)  # contract IncidentStatus
FINAL_STATUSES = (CLOSED, CANCELLED)
ACTIVE_STATUSES = (OPEN, INVESTIGATING, MITIGATED)  # counted by GET /stats/open, in its order

SEVERITIES = ("critical", "high", "medium", "low")  # contract Severity, most severe first

# POST /incidents/{id}/status: the moves the contract allows, by target status.
MOVES = {
    INVESTIGATING: (OPEN, MITIGATED, RESOLVED),
    MITIGATED: (INVESTIGATING,),
    RESOLVED: (INVESTIGATING, MITIGATED),
    CLOSED: (RESOLVED,),
    CANCELLED: (OPEN, INVESTIGATING),
}
TARGET_STATUSES = tuple(MOVES)  # contract IncidentStatusInput.status, in its order

RELATIONS = ("related_ticket", "affected_asset", "work_order")  # contract ReferenceInput.relation


def is_reopen(current: str, target: str) -> bool:
    return current == RESOLVED and target == INVESTIGATING


def move(current: str, target: str, *, resolution_summary: str | None = None, note: str | None = None) -> str:
    """The new status, or 409 when the move is not allowed from `current`, or 422 when the resolution summary (to
    resolve) or the note (to cancel or reopen) is missing."""
    if target not in MOVES:
        raise DomainRuleError("invalid_status", f"unknown status {target}", kind="invalid", field="status")
    if current not in MOVES[target]:
        raise DomainRuleError(
            "transition_not_allowed",
            f"an incident cannot move from {current} to {target}",
            kind="conflict",
            field="status",
        )
    if target == RESOLVED and not (resolution_summary or "").strip():
        raise DomainRuleError(
            "resolution_summary_required",
            "resolving needs a resolution_summary",
            kind="invalid",
            field="resolution_summary",
        )
    if target == CANCELLED and not (note or "").strip():
        raise DomainRuleError("note_required", "cancelling needs a note", kind="invalid", field="note")
    if is_reopen(current, target) and not (note or "").strip():
        raise DomainRuleError("note_required", "reopening needs a note", kind="invalid", field="note")
    return target


def check_editable(status: str) -> None:
    """PATCH /incidents/{id}, timeline updates and new references: 409 when the incident is closed or cancelled."""
    if status in FINAL_STATUSES:
        raise DomainRuleError("incident_closed", f"a {status} incident cannot be changed", kind="conflict")


def check_text(value: str, field: str) -> None:
    """A required text that is only spaces is as good as missing (422)."""
    if not value.strip():
        raise DomainRuleError(f"{field}_blank", f"{field} cannot be blank", kind="invalid", field=field)
