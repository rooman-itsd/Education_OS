"""Open tickets counted per priority (contract `OpenByPriority`, GET /stats/open-by-priority; PRD "Dashboard
widget", helpdesk.open-by-priority).

open_by_priority counts the tickets it is given. Choosing those tickets is not done here: scope=mine ("tickets
assigned to the caller"), my_queues ("tickets in the caller's queues"), all ("every queue", which needs
helpdesk:ticket:read-all, otherwise 403) and the queue_id filter depend on the caller's permissions and queue
membership, which the application layer resolves before calling this.

The contract gives total_open and oldest_created_at a name and a type only. They are computed as follows:

- total_open is the sum of the rows' open. Ticket.priority is required and the rows cover every Priority, so each
  open ticket counted is in exactly one row.
- oldest_created_at is the earliest created_at among the row's open tickets, and null for a row with none (the
  field is nullable). Other modules' oldest_* counts mean the same: the oldest of the items counted (lms and
  examinations PRDs).
- Tickets that are resolved, closed or cancelled are valid tickets that are simply not open, so they are skipped
  rather than rejected. The PRD has the endpoint read open tickets only ("without scanning closed tickets"). An
  unknown status or priority is still an error."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from .errors import DomainRuleError
from .tickets import ON_HOLD, OPEN_STATUSES, PRIORITIES, PRIORITIES_URGENT_FIRST, require_status

MINE, MY_QUEUES, ALL = "mine", "my_queues", "all"
SCOPES = (MINE, MY_QUEUES, ALL)  # GET /stats/open-by-priority `scope`, OpenByPriority.scope
DEFAULT_SCOPE = MY_QUEUES  # "my_queues (default)"


@dataclass(frozen=True)
class CountedTicket:
    """The fields of a ticket the counts need (contract `Ticket`: status, priority, assignee_id, created_at)."""

    status: str
    priority: str
    assignee_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class PriorityRow:
    """One item of OpenByPriority.rows."""

    priority: str
    open: int  # "new + in_progress + on_hold"
    unassigned: int
    assigned_to_me: int
    on_hold: int
    oldest_created_at: datetime | None


@dataclass(frozen=True)
class OpenByPriority:
    scope: str
    total_open: int
    rows: tuple[PriorityRow, ...]


def require_scope(scope: object) -> str:
    """The value is one of the endpoint's scopes."""
    if not isinstance(scope, str) or scope not in SCOPES:
        raise DomainRuleError("invalid_scope", "scope must be mine, my_queues or all", kind="invalid", field="scope")
    return scope


def open_by_priority(tickets: Iterable[CountedTicket], *, scope: str, caller_id: str) -> OpenByPriority:
    """Open tickets ("new, in_progress, on_hold") counted per priority, urgent first, with unassigned and
    assigned-to-caller counts. Every priority has a row; "priorities with no open tickets have zero counts".
    total_open, oldest_created_at and tickets that are not open: see the module docstring."""
    scope = require_scope(scope)
    counted: dict[str, list[CountedTicket]] = {priority: [] for priority in PRIORITIES}
    for ticket in tickets:
        status = require_status(ticket.status)
        if ticket.priority not in counted:
            message = "priority must be a Priority"
            raise DomainRuleError("invalid_priority", message, kind="invalid", field="priority")
        if status in OPEN_STATUSES:
            counted[ticket.priority].append(ticket)
    rows = tuple(_row(priority, counted[priority], caller_id) for priority in PRIORITIES_URGENT_FIRST)
    return OpenByPriority(scope=scope, total_open=sum(row.open for row in rows), rows=rows)


def _row(priority: str, tickets: list[CountedTicket], caller_id: str) -> PriorityRow:
    return PriorityRow(
        priority=priority,
        open=len(tickets),
        unassigned=sum(1 for t in tickets if t.assignee_id is None),
        assigned_to_me=sum(1 for t in tickets if t.assignee_id is not None and t.assignee_id == caller_id),
        on_hold=sum(1 for t in tickets if t.status == ON_HOLD),
        oldest_created_at=min((t.created_at for t in tickets), default=None),
    )
