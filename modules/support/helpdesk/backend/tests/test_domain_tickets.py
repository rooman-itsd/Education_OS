"""Unit tests of the ticket status rules (domain layer): every status against every operation, with the expected
result written out from contracts/openapi.yaml rather than taken from the module's own tables."""

import pytest
from eos_helpdesk.domain.errors import KINDS, DomainRuleError
from eos_helpdesk.domain.tickets import (
    FINAL_STATUSES,
    HOLD_REASONS,
    OPEN_STATUSES,
    PRIORITIES,
    PRIORITIES_URGENT_FIRST,
    TICKET_STATUSES,
    WAITING_INTERNAL,
    WAITING_REQUESTER,
    WAITING_THIRD_PARTY,
    cancel,
    close,
    ensure_can_comment,
    ensure_can_reclassify,
    put_on_hold,
    reopen,
    require_status,
    resolve,
    start_work,
    status_after_agent_public_reply,
    status_after_requester_reply,
    withdraw,
)

CONFLICT = "conflict"


def error_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return (err.value.code, err.value.kind, err.value.field)


def outcome(fn):
    """The new status, or the error kind when the move is refused."""
    try:
        return fn()
    except DomainRuleError as err:
        return err.kind


# --- the contract's enums


def test_statuses_priorities_and_hold_reasons_are_the_contract_enums():
    assert TICKET_STATUSES == ("new", "in_progress", "on_hold", "resolved", "closed", "cancelled")
    assert PRIORITIES == ("low", "medium", "high", "urgent")
    assert HOLD_REASONS == ("waiting_requester", "waiting_third_party", "waiting_internal")


def test_open_and_final_statuses():
    assert OPEN_STATUSES == ("new", "in_progress", "on_hold")
    assert FINAL_STATUSES == ("closed", "cancelled")


def test_priorities_urgent_first_holds_every_priority_once():
    assert PRIORITIES_URGENT_FIRST == ("urgent", "high", "medium", "low")
    assert sorted(PRIORITIES_URGENT_FIRST) == sorted(PRIORITIES)


@pytest.mark.parametrize("value", ["", "open", "NEW", None, 1])
def test_unknown_status_is_invalid(value):
    assert error_of(lambda: require_status(value)) == ("invalid_status", "invalid", "status")
    assert error_of(lambda: resolve(value)) == ("invalid_status", "invalid", "status")


def test_error_kinds_are_fixed():
    assert KINDS == ("invalid", "conflict")
    with pytest.raises(ValueError):
        DomainRuleError("x", "y", kind="unexpected")


# --- every status against every move

MOVES = {
    # POST /tickets/{id}/status in_progress: "new or on_hold → in_progress"
    "start_work": (
        start_work,
        {"new": "in_progress", "on_hold": "in_progress"},
    ),
    # POST /tickets/{id}/status on_hold: "in_progress → on_hold"
    "put_on_hold": (
        lambda s: put_on_hold(s, WAITING_THIRD_PARTY),
        {"in_progress": "on_hold"},
    ),
    # POST /tickets/{id}/resolve: "new, in_progress or on_hold → resolved"
    "resolve": (
        resolve,
        {"new": "resolved", "in_progress": "resolved", "on_hold": "resolved"},
    ),
    # POST /me/tickets/{id}/confirm "resolved → closed", and the daily auto-close
    "close": (close, {"resolved": "closed"}),
    # POST /me/tickets/{id}/reopen: "resolved → in_progress"
    "reopen": (reopen, {"resolved": "in_progress"}),
    # POST /me/tickets/{id}/withdraw: "before it is resolved"
    "withdraw": (
        withdraw,
        {"new": "cancelled", "in_progress": "cancelled", "on_hold": "cancelled"},
    ),
    # POST /tickets/{id}/cancel: 409 when "Already resolved, closed or cancelled"
    "cancel": (
        lambda s: cancel(s, ticket_id="t1"),
        {"new": "cancelled", "in_progress": "cancelled", "on_hold": "cancelled"},
    ),
}


@pytest.mark.parametrize("move", sorted(MOVES))
@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold", "resolved", "closed", "cancelled"])
def test_every_move_from_every_status(move, status):
    fn, allowed = MOVES[move]
    assert outcome(lambda: fn(status)) == allowed.get(status, CONFLICT)


def test_a_refused_move_names_the_rule():
    assert error_of(lambda: resolve("closed")) == ("transition_not_allowed", "conflict", "status")


@pytest.mark.parametrize("status", ["closed", "cancelled"])
def test_final_statuses_allow_no_move(status):
    for fn, _ in MOVES.values():
        assert outcome(lambda fn=fn: fn(status)) == CONFLICT


# --- hold reason (StatusInput: "Required when status is on_hold")


@pytest.mark.parametrize("reason", [WAITING_REQUESTER, WAITING_THIRD_PARTY, WAITING_INTERNAL])
def test_every_hold_reason_is_accepted(reason):
    assert put_on_hold("in_progress", reason) == "on_hold"


def test_hold_without_a_reason_is_invalid():
    assert error_of(lambda: put_on_hold("in_progress", None)) == ("hold_reason_required", "invalid", "hold_reason")


@pytest.mark.parametrize("reason", ["", "waiting", "WAITING_REQUESTER", 3])
def test_hold_with_an_unknown_reason_is_invalid(reason):
    assert error_of(lambda: put_on_hold("in_progress", reason)) == ("invalid_hold_reason", "invalid", "hold_reason")


# --- cancel as a duplicate


def test_a_ticket_cannot_duplicate_itself():
    refused = error_of(lambda: cancel("new", ticket_id="t1", duplicate_of="t1"))
    assert refused == ("duplicate_of_itself", "conflict", "duplicate_of")


def test_cancel_as_a_duplicate_of_another_ticket():
    assert cancel("in_progress", ticket_id="t1", duplicate_of="t2") == "cancelled"


# --- replies and notes (409 when "Ticket is closed or cancelled")


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold", "resolved"])
def test_replies_and_notes_are_allowed_until_closed_or_cancelled(status):
    ensure_can_comment(status)


@pytest.mark.parametrize("status", ["closed", "cancelled"])
def test_no_replies_or_notes_on_a_closed_or_cancelled_ticket(status):
    assert error_of(lambda: ensure_can_comment(status)) == ("ticket_final", "conflict", "status")
    assert outcome(lambda: status_after_agent_public_reply(status)) == CONFLICT
    assert outcome(lambda: status_after_requester_reply(status, None)) == CONFLICT


@pytest.mark.parametrize(
    ("status", "after"),
    [("new", "in_progress"), ("in_progress", "in_progress"), ("on_hold", "on_hold"), ("resolved", "resolved")],
)
def test_an_agent_public_reply_moves_only_a_new_ticket(status, after):
    assert status_after_agent_public_reply(status) == after


@pytest.mark.parametrize(
    ("status", "hold_reason", "after"),
    [
        ("on_hold", WAITING_REQUESTER, "in_progress"),
        ("on_hold", WAITING_THIRD_PARTY, "on_hold"),
        ("on_hold", WAITING_INTERNAL, "on_hold"),
        ("new", None, "new"),
        ("in_progress", None, "in_progress"),
        ("resolved", None, "resolved"),
    ],
)
def test_a_requester_reply_moves_only_a_ticket_waiting_on_them(status, hold_reason, after):
    assert status_after_requester_reply(status, hold_reason) == after


# --- reclassify (PATCH /tickets/{id}: 409 when "Ticket is resolved, closed or cancelled")


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold"])
def test_open_tickets_can_be_reclassified(status):
    ensure_can_reclassify(status)


@pytest.mark.parametrize("status", ["resolved", "closed", "cancelled"])
def test_resolved_closed_or_cancelled_tickets_cannot_be_reclassified(status):
    assert error_of(lambda: ensure_can_reclassify(status)) == ("transition_not_allowed", "conflict", "status")
