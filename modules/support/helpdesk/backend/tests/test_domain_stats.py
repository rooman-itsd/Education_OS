"""Unit tests of the open-by-priority counts (domain layer): contract OpenByPriority behind the Support Staff widget
helpdesk.open-by-priority. total_open, oldest_created_at and tickets that are not open follow the rules in the
eos_helpdesk.domain.stats docstring."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from eos_helpdesk.domain.errors import DomainRuleError
from eos_helpdesk.domain.stats import (
    ALL,
    DEFAULT_SCOPE,
    MINE,
    MY_QUEUES,
    SCOPES,
    CountedTicket,
    PriorityRow,
    open_by_priority,
    require_scope,
)

ME, OTHER = "agent-1", "agent-2"
DAY1 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
DAY2 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
DAY3 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
EMPTY = {p: PriorityRow(p, 0, 0, 0, 0, None) for p in ("urgent", "high", "medium", "low")}


def ticket(status="new", priority="medium", assignee_id=None, created_at=DAY2):
    return CountedTicket(status=status, priority=priority, assignee_id=assignee_id, created_at=created_at)


def counts(tickets, scope=MY_QUEUES, caller_id=ME):
    return open_by_priority(tickets, scope=scope, caller_id=caller_id)


def row(result, priority):
    return next(r for r in result.rows if r.priority == priority)


def error_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return (err.value.code, err.value.kind, err.value.field)


# --- scope


def test_scopes_are_the_contract_enum_with_my_queues_by_default():
    assert SCOPES == ("mine", "my_queues", "all")
    assert DEFAULT_SCOPE == "my_queues"


@pytest.mark.parametrize("scope", [MINE, MY_QUEUES, ALL])
def test_the_scope_is_returned_as_given(scope):
    assert counts([], scope=scope).scope == scope


@pytest.mark.parametrize("scope", ["", "queue", "ALL", None])
def test_an_unknown_scope_is_invalid(scope):
    assert error_of(lambda: require_scope(scope)) == ("invalid_scope", "invalid", "scope")
    assert error_of(lambda: counts([], scope=scope)) == ("invalid_scope", "invalid", "scope")


# --- rows: "One row per priority, urgent first; priorities with no open tickets have zero counts"


def test_no_tickets_gives_a_zero_row_for_every_priority_urgent_first():
    result = counts([])
    assert result.total_open == 0
    assert result.rows == (EMPTY["urgent"], EMPTY["high"], EMPTY["medium"], EMPTY["low"])


def test_rows_stay_urgent_first_whatever_order_the_tickets_come_in():
    result = counts([ticket(priority="low"), ticket(priority="urgent"), ticket(priority="medium")])
    assert [r.priority for r in result.rows] == ["urgent", "high", "medium", "low"]


def test_priorities_without_open_tickets_keep_a_zero_row_next_to_counted_ones():
    result = counts([ticket(priority="high"), ticket(priority="high", status="on_hold")])
    assert row(result, "high") == PriorityRow("high", 2, 2, 0, 1, DAY2)
    assert [row(result, p) for p in ("urgent", "medium", "low")] == [EMPTY["urgent"], EMPTY["medium"], EMPTY["low"]]


# --- what counts as open: "new + in_progress + on_hold"


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold"])
def test_open_statuses_are_counted(status):
    assert row(counts([ticket(status=status)]), "medium").open == 1


@pytest.mark.parametrize("status", ["resolved", "closed", "cancelled"])
def test_tickets_that_are_not_open_are_skipped(status):
    result = counts([ticket(status=status)])
    assert result.total_open == 0
    assert row(result, "medium") == EMPTY["medium"]


def test_a_priority_whose_tickets_are_all_closed_has_a_zero_row():
    tickets = [ticket(priority="low", status=s) for s in ("resolved", "closed", "cancelled")]
    tickets.append(ticket(priority="urgent"))
    result = counts(tickets)
    assert row(result, "low") == EMPTY["low"]
    assert result.total_open == 1


def test_counts_per_priority_with_open_and_closed_tickets_mixed():
    tickets = [
        ticket(status="new", priority="urgent", assignee_id=None, created_at=DAY2),
        ticket(status="on_hold", priority="urgent", assignee_id=ME, created_at=DAY1),
        ticket(status="in_progress", priority="urgent", assignee_id=OTHER, created_at=DAY3),
        ticket(status="resolved", priority="urgent", assignee_id=ME, created_at=DAY1),
        ticket(status="closed", priority="high", assignee_id=None, created_at=DAY1),
        ticket(status="cancelled", priority="medium", assignee_id=ME, created_at=DAY1),
        ticket(status="in_progress", priority="low", assignee_id=ME, created_at=DAY3),
        ticket(status="on_hold", priority="low", assignee_id=None, created_at=DAY2),
    ]
    result = counts(tickets)
    assert result.rows == (
        PriorityRow("urgent", 3, 1, 1, 1, DAY1),
        EMPTY["high"],
        EMPTY["medium"],
        PriorityRow("low", 2, 1, 1, 1, DAY2),
    )
    assert result.total_open == 5


def test_total_open_is_the_sum_of_the_rows():
    tickets = [
        ticket(priority="urgent"),
        ticket(priority="high", status="in_progress"),
        ticket(priority="high", status="on_hold"),
        ticket(priority="low"),
        ticket(priority="high", status="closed"),
    ]
    result = counts(tickets)
    assert result.total_open == 4 == sum(r.open for r in result.rows)


# --- unassigned and assigned to the caller


def test_assigned_to_me_follows_the_caller():
    tickets = [ticket(assignee_id=ME), ticket(assignee_id=OTHER), ticket(assignee_id=None)]
    assert row(counts(tickets, caller_id=ME), "medium").assigned_to_me == 1
    assert row(counts(tickets, caller_id=OTHER), "medium").assigned_to_me == 1
    assert row(counts(tickets, caller_id="agent-3"), "medium").assigned_to_me == 0


def test_unassigned_counts_tickets_without_an_assignee():
    tickets = [ticket(assignee_id=None), ticket(assignee_id=None), ticket(assignee_id=ME)]
    assert row(counts(tickets), "medium").unassigned == 2


def test_closed_tickets_assigned_to_me_are_not_counted():
    tickets = [ticket(assignee_id=ME, status="closed"), ticket(assignee_id=None, status="resolved")]
    assert row(counts(tickets), "medium") == EMPTY["medium"]


# --- oldest open ticket per priority


def test_oldest_created_at_is_the_earliest_open_ticket_of_the_priority():
    tickets = [
        ticket(priority="high", created_at=DAY3),
        ticket(priority="high", created_at=DAY1),
        ticket(priority="high", status="closed", created_at=datetime(2026, 9, 1, tzinfo=UTC)),
    ]
    assert row(counts(tickets), "high").oldest_created_at == DAY1


def test_oldest_created_at_is_kept_per_priority():
    tickets = [ticket(priority="urgent", created_at=DAY3), ticket(priority="low", created_at=DAY1)]
    result = counts(tickets)
    assert row(result, "urgent").oldest_created_at == DAY3
    assert row(result, "low").oldest_created_at == DAY1


def test_oldest_created_at_is_null_when_only_closed_tickets_are_older():
    tickets = [ticket(priority="high", status="closed", created_at=DAY1)]
    assert row(counts(tickets), "high").oldest_created_at is None


def test_oldest_created_at_compares_instants_across_offsets():
    ist = timezone(timedelta(hours=5, minutes=30))
    earlier = datetime(2026, 10, 2, 12, 0, tzinfo=ist)  # 06:30 UTC
    later = datetime(2026, 10, 2, 7, 0, tzinfo=UTC)
    tickets = [ticket(created_at=later), ticket(created_at=earlier)]
    assert row(counts(tickets), "medium").oldest_created_at == earlier


def test_tickets_created_at_the_same_time_share_the_oldest_date():
    tickets = [ticket(created_at=DAY1), ticket(created_at=DAY1, status="on_hold")]
    assert row(counts(tickets), "medium").oldest_created_at == DAY1


# --- input values


def test_an_unknown_status_is_invalid():
    assert error_of(lambda: counts([ticket(status="open")])) == ("invalid_status", "invalid", "status")


def test_an_unknown_priority_is_invalid():
    assert error_of(lambda: counts([ticket(priority="critical")])) == ("invalid_priority", "invalid", "priority")


def test_an_unknown_priority_is_invalid_even_on_a_closed_ticket():
    assert error_of(lambda: counts([ticket(priority="critical", status="closed")]))[0] == "invalid_priority"
