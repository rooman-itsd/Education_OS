"""Unit tests of attendance report arithmetic (domain layer): FR-13, FR-14, FR-18."""

from decimal import Decimal

import pytest
from eos_timetable_attendance.domain.reports import Tally, no_eligible_classes, tally


def test_attended_is_present_plus_late_and_excused_leaves_the_denominator():
    t = tally(["present", "present", "late", "absent", "excused", "excused"])
    assert (t.present, t.late, t.absent, t.excused) == (2, 1, 1, 2)
    assert (t.attended, t.held) == (3, 4)
    assert t.percentage == Decimal("75.00")


def test_percentage_rounds_halves_up_to_two_places():
    assert tally(["present"] + ["absent"] * 2).percentage == Decimal("33.33")
    assert tally(["present"] * 2 + ["absent"]).percentage == Decimal("66.67")
    assert Tally(present=1, absent=7).percentage == Decimal("12.50")
    assert Tally(present=1, absent=15).percentage == Decimal("6.25")


def test_nothing_held_has_no_percentage_and_is_flagged_for_eligibility():
    for t in (tally([]), tally(["excused"])):
        assert t.percentage is None
        assert no_eligible_classes(t)
        assert not t.below(75)
    assert not no_eligible_classes(tally(["absent"]))


@pytest.mark.parametrize(
    ("present", "absent", "short"),
    [(3, 1, False), (2, 1, True), (75, 25, False), (74, 26, True), (0, 1, True), (1, 0, False)],
)
def test_shortage_is_below_the_threshold_and_exactly_the_threshold_is_not_short(present, absent, short):
    assert Tally(present=present, absent=absent).below(75) is short


def test_shortage_uses_the_unrounded_value():
    t = Tally(present=74999, absent=25001)  # 74.999 prints as 75.00 but is below 75
    assert t.percentage == Decimal("75.00")
    assert t.below(75)


def test_threshold_of_zero_never_flags_and_100_flags_any_absence():
    assert not Tally(absent=5).below(0)
    assert Tally(present=9, absent=1).below(100)
    assert not Tally(present=10).below(100)


def test_tallies_add_up_across_sections_or_courses():
    total = tally(["present", "absent"]).plus(tally(["late", "excused"]))
    assert (total.present, total.late, total.absent, total.excused) == (1, 1, 1, 1)


def test_an_unknown_status_is_a_programming_error():
    with pytest.raises(ValueError, match="unknown attendance status"):
        tally(["present", "asleep"])
