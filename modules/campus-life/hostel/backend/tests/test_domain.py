"""Domain rules, without the database or HTTP."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_hostel.domain import rules
from eos_hostel.domain.rules import ALLOCATION_TRANSITIONS, LEAVE_TRANSITIONS, Period, RuleViolationError

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)


def test_beds_are_numbered_from_one():
    assert rules.bed_labels(3) == ["1", "2", "3"]
    assert rules.free_beds(3, ["2"]) == ["1", "3"]
    rules.check_bed(2, "2")
    with pytest.raises(RuleViolationError) as e:
        rules.check_bed(2, "3")
    assert e.value.code == "invalid_bed"


def test_capacity_cannot_drop_below_occupancy_or_a_held_bed():
    rules.check_capacity_change(2, ["1", "2"])
    with pytest.raises(RuleViolationError):
        rules.check_capacity_change(1, ["1", "2"])
    with pytest.raises(RuleViolationError):
        rules.check_capacity_change(2, ["3"])  # one held bed, but bed 3 would no longer exist


def test_periods_overlap_including_open_ended():
    oct_ = Period(date(2026, 10, 1), date(2026, 10, 31))
    assert oct_.overlaps(Period(date(2026, 10, 31), date(2026, 11, 30)))
    assert not oct_.overlaps(Period(date(2026, 11, 1), date(2026, 11, 30)))
    assert oct_.overlaps(Period(date(2026, 9, 1)))  # open-ended
    with pytest.raises(RuleViolationError):
        rules.check_period(date(2026, 10, 2), date(2026, 10, 1))


@pytest.mark.parametrize(
    ("action", "current", "expected"),
    [
        ("confirm", "requested", "confirmed"),
        ("check_in", "confirmed", "occupied"),
        ("check_out", "occupied", "vacated"),
        ("cancel", "requested", "cancelled"),
        ("cancel", "confirmed", "cancelled"),
    ],
)
def test_allocation_lifecycle(action, current, expected):
    assert rules.transition(ALLOCATION_TRANSITIONS, action, current) == expected


@pytest.mark.parametrize(
    ("action", "current"),
    [("check_in", "requested"), ("check_out", "confirmed"), ("cancel", "occupied"), ("cancel", "vacated")],
)
def test_allocation_refuses_out_of_order(action, current):
    with pytest.raises(RuleViolationError) as e:
        rules.transition(ALLOCATION_TRANSITIONS, action, current)
    assert e.value.code == "invalid_status"


def test_leave_lifecycle():
    assert rules.transition(LEAVE_TRANSITIONS, "approve", "requested") == "approved"
    assert rules.transition(LEAVE_TRANSITIONS, "reject", "requested") == "rejected"
    assert rules.transition(LEAVE_TRANSITIONS, "withdraw", "requested") == "withdrawn"
    assert rules.transition(LEAVE_TRANSITIONS, "return", "approved") == "returned"
    # Gate pass: security records the departure and the return; the warden may close an out leave too.
    assert rules.transition(LEAVE_TRANSITIONS, "gate_out", "approved") == "out"
    assert rules.transition(LEAVE_TRANSITIONS, "gate_in", "out") == "returned"
    assert rules.transition(LEAVE_TRANSITIONS, "return", "out") == "returned"
    for action, current in (
        ("withdraw", "approved"),
        ("return", "requested"),
        ("approve", "rejected"),
        ("gate_out", "requested"),
        ("gate_out", "out"),
        ("gate_in", "approved"),
        ("withdraw", "out"),
    ):
        with pytest.raises(RuleViolationError):
            rules.transition(LEAVE_TRANSITIONS, action, current)


def test_leave_window_and_overdue():
    with pytest.raises(RuleViolationError):
        rules.check_leave_window(NOW, NOW)
    assert rules.windows_overlap(NOW, NOW + timedelta(hours=4), NOW + timedelta(hours=3), NOW + timedelta(hours=5))
    assert not rules.windows_overlap(NOW, NOW + timedelta(hours=4), NOW + timedelta(hours=4), NOW + timedelta(hours=5))
    assert rules.is_overdue("approved", NOW - timedelta(minutes=1), NOW)
    assert rules.is_overdue("out", NOW - timedelta(minutes=1), NOW)
    assert not rules.is_overdue("returned", NOW - timedelta(minutes=1), NOW)
    assert not rules.is_overdue("approved", NOW + timedelta(minutes=1), NOW)


def test_nobody_decides_their_own_leave():
    with pytest.raises(RuleViolationError) as e:
        rules.check_not_own_decision("u1", "u1")
    assert e.value.code == "own_request"
    rules.check_not_own_decision("u1", "u2")


def test_id_document_note_keeps_only_last_digits():
    rules.check_id_document_note("Aadhaar ending 1234")
    rules.check_id_document_note(None)
    with pytest.raises(RuleViolationError):
        rules.check_id_document_note("Aadhaar 1234 5678 9012")


def test_notice_status_and_visibility():
    assert rules.notice_status(None, None, NOW) == "current"
    assert rules.notice_status(None, NOW, NOW) == "expired"
    assert rules.notice_status(NOW, NOW + timedelta(days=1), NOW) == "withdrawn"
    assert rules.notice_visible_to(None, None)
    assert rules.notice_visible_to("h1", "h1")
    assert not rules.notice_visible_to("h1", "h2")
    assert not rules.notice_visible_to("h1", None)
