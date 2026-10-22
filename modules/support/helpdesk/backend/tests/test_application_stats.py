"""Unit tests of GET /stats/open-by-priority as a use case (application layer): permission, scope, the queue_id
filter and what is asked of storage. Storage is a fake that records the query and filters like a repository would."""

from datetime import UTC, datetime

import pytest
from eos_helpdesk.application.access import TICKET_READ, TICKET_READ_ALL, Actor
from eos_helpdesk.application.errors import HelpdeskError
from eos_helpdesk.application.stats import get_open_by_priority
from eos_helpdesk.domain.stats import CountedTicket

ME, OTHER = "agent-1", "agent-2"
WHEN = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
# (queue_id, ticket): the organisation's open tickets
STORED = [
    ("q-it", CountedTicket("new", "urgent", None, WHEN)),
    ("q-it", CountedTicket("in_progress", "high", ME, WHEN)),
    ("q-accounts", CountedTicket("on_hold", "low", ME, WHEN)),
    ("q-accounts", CountedTicket("new", "low", OTHER, WHEN)),
    ("q-office", CountedTicket("new", "medium", None, WHEN)),
]


class FakeStorage:
    def __init__(self):
        self.queries = []

    def find_open_tickets(self, queue_ids, assignee_id):
        self.queries.append((queue_ids, assignee_id))
        return [
            t
            for queue, t in STORED
            if (queue_ids is None or queue in queue_ids) and (assignee_id is None or t.assignee_id == assignee_id)
        ]


def actor(*permissions):
    return Actor(user_id=ME, organisation_id="org-1", permissions=set(permissions))


AGENT = actor(TICKET_READ)
LEAD = actor(TICKET_READ, TICKET_READ_ALL)


def run(who, scope=None, queue_id=None, member_of=("q-it", "q-accounts")):
    storage = FakeStorage()
    result = get_open_by_priority(
        who, scope=scope, queue_id=queue_id, caller_queue_ids=member_of, find_open_tickets=storage.find_open_tickets
    )
    return result, storage.queries


def open_per_priority(result):
    return {r.priority: r.open for r in result.rows}


# --- permission: "Permission helpdesk:ticket:read"; 403 "scope=all without helpdesk:ticket:read-all"


def test_without_ticket_read_the_caller_is_forbidden():
    with pytest.raises(HelpdeskError) as err:
        run(actor())
    assert err.value.status == 403


def test_scope_all_without_read_all_is_forbidden():
    with pytest.raises(HelpdeskError) as err:
        run(AGENT, scope="all")
    assert (err.value.status, err.value.code) == (403, "forbidden")


def test_an_unknown_scope_is_refused_as_invalid():
    with pytest.raises(HelpdeskError) as err:
        run(AGENT, scope="everything")
    assert (err.value.status, err.value.code, err.value.field) == (422, "invalid_scope", "scope")


# --- scope: "mine counts tickets assigned to the caller; my_queues (default) tickets in the caller's queues; all
# every queue"


def test_my_queues_is_the_default():
    result, queries = run(AGENT)
    assert result.scope == "my_queues"
    assert queries == [(frozenset({"q-it", "q-accounts"}), None)]
    assert open_per_priority(result) == {"urgent": 1, "high": 1, "medium": 0, "low": 2}


def test_mine_counts_tickets_assigned_to_the_caller_in_any_queue():
    result, queries = run(AGENT, scope="mine", member_of=())
    assert queries == [(None, ME)]
    assert open_per_priority(result) == {"urgent": 0, "high": 1, "medium": 0, "low": 1}
    assert result.total_open == 2


def test_all_counts_every_queue_for_a_caller_with_read_all():
    result, queries = run(LEAD, scope="all", member_of=())
    assert queries == [(None, None)]
    assert result.total_open == 5


def test_a_lead_asking_for_my_queues_gets_their_own_queues_only():
    result, _ = run(LEAD, scope="my_queues", member_of=("q-office",))
    assert open_per_priority(result) == {"urgent": 0, "high": 0, "medium": 1, "low": 0}


def test_an_agent_in_no_queue_gets_zero_counts_without_a_query():
    result, queries = run(AGENT, member_of=())
    assert queries == []
    assert result.total_open == 0
    assert [r.priority for r in result.rows] == ["urgent", "high", "medium", "low"]


def test_assigned_to_me_is_counted_for_the_caller():
    result, _ = run(AGENT)
    rows = {r.priority: r for r in result.rows}
    assert (rows["high"].assigned_to_me, rows["low"].assigned_to_me, rows["low"].unassigned) == (1, 1, 0)


# --- queue_id: "Narrow to one queue the caller may see"


def test_queue_id_narrows_my_queues_to_that_queue():
    result, queries = run(AGENT, queue_id="q-accounts")
    assert queries == [(frozenset({"q-accounts"}), None)]
    assert open_per_priority(result) == {"urgent": 0, "high": 0, "medium": 0, "low": 2}


def test_queue_id_narrows_mine_to_that_queue():
    result, queries = run(AGENT, scope="mine", queue_id="q-it")
    assert queries == [(frozenset({"q-it"}), ME)]
    assert result.total_open == 1


def test_a_lead_can_narrow_all_to_any_queue():
    result, queries = run(LEAD, scope="all", queue_id="q-office", member_of=())
    assert queries == [(frozenset({"q-office"}), None)]
    assert result.total_open == 1


def test_a_queue_the_caller_may_not_see_adds_nothing():
    result, queries = run(AGENT, queue_id="q-office")
    assert queries == []
    assert result.total_open == 0
    result, queries = run(AGENT, scope="mine", queue_id="q-office")
    assert (queries, result.total_open) == ([], 0)


def test_my_queues_narrowed_to_a_queue_outside_them_adds_nothing_even_for_a_lead():
    result, queries = run(LEAD, scope="my_queues", queue_id="q-office", member_of=("q-it",))
    assert (queries, result.total_open) == ([], 0)
