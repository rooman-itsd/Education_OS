"""Domain rules: contract statuses and edits, expiry worked out when read, engagement moves and within_terms, and the
expiring-contracts statistics."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_amc_vendor_support.domain import contracts as c
from eos_amc_vendor_support.domain import engagements as e
from eos_amc_vendor_support.domain.errors import DomainRuleError
from eos_amc_vendor_support.domain.expiring import ContractForExpiry, contracts_expiring

TODAY = date(2026, 11, 1)
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def kind_of(fn, *args, **kwargs) -> tuple[str, str]:
    with pytest.raises(DomainRuleError) as err:
        fn(*args, **kwargs)
    return err.value.kind, err.value.code


# ---------------------------------------------------------------- contracts


def test_end_date_must_be_after_start_date():
    c.check_period(date(2026, 1, 1), date(2026, 1, 2))
    assert kind_of(c.check_period, date(2026, 1, 1), date(2026, 1, 1)) == ("invalid", "end_before_start")
    assert kind_of(c.check_period, date(2026, 1, 2), date(2026, 1, 1)) == ("invalid", "end_before_start")


def test_draft_edits_anything_active_only_owner_contacts_and_notice():
    c.check_editable(c.DRAFT, {"title", "end_date", "value"})
    c.check_editable(c.ACTIVE, {"owner_id", "vendor_contacts", "renewal_notice_days"})
    assert kind_of(c.check_editable, c.ACTIVE, {"owner_id", "end_date"}) == ("conflict", "field_not_editable")
    for closed in (c.TERMINATED, c.RENEWED):
        assert kind_of(c.check_editable, closed, {"owner_id"}) == ("conflict", "contract_closed")


def test_activate_and_terminate_moves():
    assert c.activate(c.DRAFT) == c.ACTIVE
    for status in (c.ACTIVE, c.TERMINATED, c.RENEWED):
        assert kind_of(c.activate, status) == ("conflict", "not_draft")
    assert c.terminate(c.ACTIVE) == c.TERMINATED
    for status in (c.DRAFT, c.TERMINATED, c.RENEWED):
        assert kind_of(c.terminate, status) == ("conflict", "not_active")


def test_renewal_needs_an_active_contract_without_a_successor():
    c.check_renewable(c.ACTIVE, None)
    assert kind_of(c.check_renewable, c.DRAFT, None) == ("conflict", "not_active")
    assert kind_of(c.check_renewable, c.ACTIVE, "successor-id") == ("conflict", "successor_exists")
    c.check_predecessor_active(c.ACTIVE)
    assert kind_of(c.check_predecessor_active, c.TERMINATED) == ("conflict", "predecessor_not_active")


def test_covered_items_change_only_on_draft_or_active():
    c.check_items_changeable(c.DRAFT)
    c.check_items_changeable(c.ACTIVE)
    assert kind_of(c.check_items_changeable, c.RENEWED) == ("conflict", "contract_closed")


def test_expired_is_active_and_past_end_date_the_end_date_itself_still_covered():
    assert not c.is_expired(c.ACTIVE, TODAY, TODAY)
    assert c.is_expired(c.ACTIVE, TODAY - timedelta(days=1), TODAY)
    assert not c.is_expired(c.DRAFT, TODAY - timedelta(days=1), TODAY)
    assert not c.is_expired(c.TERMINATED, TODAY - timedelta(days=1), TODAY)


def test_expiring_is_active_within_the_notice_and_not_yet_past():
    assert c.is_expiring(c.ACTIVE, TODAY + timedelta(days=60), 60, TODAY)
    assert not c.is_expiring(c.ACTIVE, TODAY + timedelta(days=61), 60, TODAY)
    assert c.is_expiring(c.ACTIVE, TODAY, 0, TODAY)
    assert not c.is_expiring(c.ACTIVE, TODAY - timedelta(days=1), 60, TODAY)  # expired, not expiring
    assert not c.is_expiring(c.DRAFT, TODAY + timedelta(days=5), 60, TODAY)


def test_engagements_only_on_active_unexpired_contracts():
    c.check_can_raise_engagement(c.ACTIVE, TODAY, TODAY)
    assert kind_of(c.check_can_raise_engagement, c.DRAFT, TODAY, TODAY) == ("conflict", "contract_not_active")
    assert kind_of(c.check_can_raise_engagement, c.ACTIVE, TODAY - timedelta(days=1), TODAY) == (
        "conflict",
        "contract_expired",
    )


# ---------------------------------------------------------------- engagements


def test_allowed_moves():
    assert e.move(e.OPEN, e.IN_PROGRESS) == e.IN_PROGRESS
    assert e.move(e.IN_PROGRESS, e.RESOLVED, resolution_note="Rope replaced") == e.RESOLVED
    assert e.move(e.RESOLVED, e.CLOSED) == e.CLOSED
    assert e.move(e.OPEN, e.CANCELLED, note="Raised twice") == e.CANCELLED
    assert e.move(e.IN_PROGRESS, e.CANCELLED, note="Not a vendor issue") == e.CANCELLED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (e.OPEN, e.RESOLVED),
        (e.OPEN, e.CLOSED),
        (e.IN_PROGRESS, e.IN_PROGRESS),
        (e.RESOLVED, e.IN_PROGRESS),
        (e.RESOLVED, e.CANCELLED),
        (e.CLOSED, e.CANCELLED),
        (e.CANCELLED, e.IN_PROGRESS),
    ],
)
def test_refused_moves(current, target):
    assert kind_of(e.move, current, target, resolution_note="x" * 3, note="x" * 3) == (
        "conflict",
        "transition_not_allowed",
    )


def test_resolve_and_cancel_need_their_notes():
    assert kind_of(e.move, e.IN_PROGRESS, e.RESOLVED) == ("invalid", "resolution_note_required")
    assert kind_of(e.move, e.IN_PROGRESS, e.RESOLVED, resolution_note="  ") == ("invalid", "resolution_note_required")
    assert kind_of(e.move, e.OPEN, e.CANCELLED) == ("invalid", "note_required")


def test_closed_and_cancelled_engagements_are_not_edited():
    e.check_editable(e.OPEN)
    e.check_editable(e.RESOLVED)
    for status in e.FINAL_STATUSES:
        assert kind_of(e.check_editable, status) == ("conflict", "engagement_closed")


def terms(response=4, resolution=24, responded=None, resolved=None):
    hours = timedelta(hours=1)
    return e.within_terms(
        response_hours=response,
        resolution_hours=resolution,
        reported_at=T0,
        vendor_responded_at=None if responded is None else T0 + responded * hours,
        resolved_at=None if resolved is None else T0 + resolved * hours,
    )


def test_within_terms():
    assert terms(response=None, resolution=None) is None  # the contract sets no hours
    assert terms() is None  # nothing recorded yet
    assert terms(responded=3) is None  # responded in time, resolution not yet measurable
    assert terms(responded=5) is False  # late response decides it
    assert terms(responded=4, resolved=24) is True  # both exactly on the limit
    assert terms(responded=2, resolved=30) is False
    assert terms(response=None, resolution=24, resolved=10) is True  # only the terms the contract sets count
    assert terms(response=4, resolution=None, responded=1) is True


# ---------------------------------------------------------------- expiring statistics


def contract(n: int, end_offset: int, status: str = c.ACTIVE, successor: str | None = None) -> ContractForExpiry:
    return ContractForExpiry(
        contract_id=f"id-{n}",
        number=f"AMC-{n:06d}",
        vendor_id="v",
        title=f"Contract {n}",
        status=status,
        end_date=TODAY + timedelta(days=end_offset),
        successor_status=successor,
    )


def test_contracts_expiring_window_order_and_counts():
    rows = [
        contract(1, 30),
        contract(2, -3),
        contract(3, 61),  # outside a 60-day window
        contract(4, 0, successor=c.DRAFT),
        contract(5, 10, status=c.DRAFT),  # not active
        contract(6, 60, successor=c.ACTIVE),  # successor active, not a draft any more
        contract(7, -40, status=c.TERMINATED),
    ]
    result = contracts_expiring(rows, 60, TODAY)
    assert [i.number for i in result.items] == ["AMC-000002", "AMC-000004", "AMC-000001", "AMC-000006"]
    assert [i.days_left for i in result.items] == [-3, 0, 30, 60]
    assert [i.renewal_draft_exists for i in result.items] == [False, True, False, False]
    assert (result.within_days, result.expiring_count, result.expired_count) == (60, 3, 1)


def test_contracts_expiring_with_nothing_due():
    result = contracts_expiring([contract(1, 200)], 60, TODAY)
    assert (result.expiring_count, result.expired_count, result.items) == (0, 0, [])
