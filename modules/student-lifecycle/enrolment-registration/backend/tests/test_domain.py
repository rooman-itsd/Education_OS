from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from eos_enrolment_registration.domain import enums as e
from eos_enrolment_registration.domain.rules import (
    OfferingSnapshot,
    RuleViolationError,
    SectionSnapshot,
    WindowSnapshot,
    check_can_end,
    check_enrolment_active,
    check_offering,
    check_registration_confirmed,
    check_section,
    check_section_change,
    check_window,
    format_roll_number,
    is_window_open,
    rank_offerings,
    references_verified,
    validate_window,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
TERM, OTHER_TERM = "term-1", "term-2"
OFFERING = "off-1"


def code_of(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as exc:
        fn(*args)
    return exc.value.code


def offering(status: str = e.OPEN, term: str = TERM) -> OfferingSnapshot:
    return OfferingSnapshot(course_offering_id=OFFERING, academic_period_id=term, status=status)


def section(status: str = e.OPEN, capacity: int = 30, offering_id: str = OFFERING) -> SectionSnapshot:
    return SectionSnapshot(section_id="sec-a", course_offering_id=offering_id, capacity=capacity, status=status)


def window(opens: timedelta = timedelta(days=-1), closes: timedelta = timedelta(days=1)) -> WindowSnapshot:
    return WindowSnapshot(opens_at=NOW + opens, closes_at=NOW + closes)


# ---------------------------------------------------------------- enrolment


def test_only_an_active_enrolment_registers():
    check_enrolment_active(e.ACTIVE)
    for status in (e.COMPLETED, e.WITHDRAWN):
        assert code_of(check_enrolment_active, status) == "enrolment_not_active"


def test_only_an_active_enrolment_can_end():
    check_can_end(e.ACTIVE)
    for status in sorted(e.ENROLMENT_ENDED):
        assert code_of(check_can_end, status) == "enrolment_ended"


def test_roll_number_format():
    assert format_roll_number("RN", 2026, 42) == "RN2026-00042"
    assert format_roll_number("STU", 2027, 1) == "STU2027-00001"
    assert format_roll_number("RN", 2026, 123456) == "RN2026-123456"


# ---------------------------------------------------------------- windows


def test_window_must_close_after_it_opens():
    validate_window(NOW, NOW + timedelta(minutes=1))
    assert code_of(validate_window, NOW, NOW) == "invalid_window"
    assert code_of(validate_window, NOW, NOW - timedelta(days=1)) == "invalid_window"


def test_window_is_open_from_opens_at_until_before_closes_at():
    assert is_window_open(window(), NOW)
    assert is_window_open(window(opens=timedelta(0)), NOW)
    assert not is_window_open(window(closes=timedelta(0)), NOW)
    assert not is_window_open(window(opens=timedelta(hours=1)), NOW)
    assert not is_window_open(None, NOW)


def test_regular_registration_needs_an_open_window():
    check_window(e.REGULAR, window(), NOW)
    assert code_of(check_window, e.REGULAR, None, NOW) == "window_closed"
    assert code_of(check_window, e.REGULAR, window(closes=timedelta(seconds=-1)), NOW) == "window_closed"
    assert code_of(check_window, e.REGULAR, window(opens=timedelta(days=2), closes=timedelta(days=3)), NOW) == (
        "window_closed"
    )


@pytest.mark.parametrize("registration_type", sorted(e.WINDOW_EXEMPT))
def test_supplementary_and_backlog_ignore_the_window(registration_type):
    check_window(registration_type, None, NOW)
    check_window(registration_type, window(closes=timedelta(days=-1), opens=timedelta(days=-2)), NOW)


# ---------------------------------------------------------------- the roster's checks


def test_unknown_offering_and_section_are_skipped_but_unverified():
    check_offering(None, TERM)
    check_section(None, OFFERING, 10_000)
    assert references_verified(None, None) is False
    assert references_verified(offering(), None) is False
    assert references_verified(None, section()) is False
    assert references_verified(offering(), section()) is True


def test_offering_must_be_open_and_in_the_term():
    check_offering(offering(), TERM)
    assert code_of(check_offering, offering(term=OTHER_TERM), TERM) == "term_mismatch"
    for status in set(e.OFFERING_STATUSES) - {e.OPEN}:
        assert code_of(check_offering, offering(status=status), TERM) == "offering_not_open"


def test_section_must_belong_be_open_and_have_a_seat():
    check_section(section(capacity=30), OFFERING, 29)
    assert code_of(check_section, section(offering_id="off-other"), OFFERING, 0) == "section_not_in_offering"
    assert code_of(check_section, section(status="closed"), OFFERING, 0) == "section_not_open"
    assert code_of(check_section, section(capacity=30), OFFERING, 30) == "section_full"
    assert code_of(check_section, section(capacity=0), OFFERING, 0) == "section_full"


def test_section_checks_run_in_contract_order():
    closed_and_full_elsewhere = section(status="closed", capacity=0, offering_id="off-other")
    assert code_of(check_section, closed_and_full_elsewhere, OFFERING, 5) == "section_not_in_offering"
    assert code_of(check_section, section(status="closed", capacity=0), OFFERING, 5) == "section_not_open"


# ---------------------------------------------------------------- registration changes


def test_only_a_confirmed_registration_changes():
    check_registration_confirmed(e.CONFIRMED)
    assert code_of(check_registration_confirmed, e.WITHDRAWN) == "registration_not_confirmed"


def test_a_move_needs_another_section():
    check_section_change("sec-a", "sec-b")
    assert code_of(check_section_change, "sec-a", "sec-a") == "same_section"


# ---------------------------------------------------------------- report


def test_rank_offerings_busiest_first_with_stable_ties():
    counts = {"off-c": 5, "off-a": 9, "off-b": 5, "off-d": 1}
    assert rank_offerings(counts, 3) == [("off-a", 9), ("off-b", 5), ("off-c", 5)]
    assert rank_offerings(counts, 10)[-1] == ("off-d", 1)
    assert rank_offerings({}, 5) == []


def test_vocabularies_match_the_contract():
    assert e.REGISTRATION_TYPES == ("regular", "supplementary", "backlog")
    assert e.REGISTRATION_STATUSES == ("confirmed", "withdrawn")
    assert e.ENROLMENT_STATUSES == ("active", "completed", "withdrawn")
