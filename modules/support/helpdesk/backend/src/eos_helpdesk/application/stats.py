"""GET /stats/open-by-priority, behind the Support Staff widget helpdesk.open-by-priority.

"Open tickets (new, in_progress, on_hold) counted per priority ... scope=mine counts tickets assigned to the
caller; my_queues (default) tickets in the caller's queues; all every queue and needs helpdesk:ticket:read-all.
Permission helpdesk:ticket:read." queue_id narrows the counts "to one queue the caller may see": a member of the
queue, or a caller with helpdesk:ticket:read-all.

The data comes from two functions the caller passes in, so the use case needs no database:
- the caller's queues (the queues whose member_ids hold the caller);
- find_open_tickets(queue_ids, assignee_id): the organisation's open tickets, limited to those queues (None means
  every queue) and to that assignee (None means anyone).

A queue_id the caller may not see adds no tickets: the contract declares no 404 for this endpoint, and the counts
must not reveal a queue the caller cannot read."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..domain.errors import DomainRuleError
from ..domain.stats import ALL, DEFAULT_SCOPE, MINE, MY_QUEUES, CountedTicket, OpenByPriority, open_by_priority
from ..domain.stats import require_scope as require_scope_value
from .access import TICKET_READ, TICKET_READ_ALL, Actor, require
from .errors import forbidden, from_domain

FindOpenTickets = Callable[[frozenset[str] | None, str | None], Iterable[CountedTicket]]


def get_open_by_priority(
    actor: Actor,
    *,
    scope: str | None,
    queue_id: str | None,
    caller_queue_ids: Iterable[str],
    find_open_tickets: FindOpenTickets,
) -> OpenByPriority:
    require(actor, TICKET_READ)
    try:
        scope = require_scope_value(DEFAULT_SCOPE if scope is None else scope)
    except DomainRuleError as err:
        raise from_domain(err) from err
    if scope == ALL and not actor.can(TICKET_READ_ALL):
        raise forbidden("scope=all needs helpdesk:ticket:read-all")

    member_of = frozenset(caller_queue_ids)
    queues: frozenset[str] | None = member_of if scope == MY_QUEUES else None
    assignee = actor.user_id if scope == MINE else None
    if queue_id is not None:
        visible = actor.can(TICKET_READ_ALL) or queue_id in member_of
        narrowed = frozenset({queue_id}) if visible else frozenset()
        queues = narrowed if queues is None else queues & narrowed

    tickets = [] if queues == frozenset() else find_open_tickets(queues, assignee)
    # A ticket with a status or priority outside the contract comes from storage, not the request, so its
    # DomainRuleError is left to surface as a server fault rather than mapped to a 4xx.
    return open_by_priority(tickets, scope=scope, caller_id=actor.user_id)
