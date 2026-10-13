"""Unit tests of the faculty load rule (domain layer): FR-13 sum of contact hours, flagged over the maximum."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.load import FacultyLoad, LoadEntry, faculty_load


def entry(faculty, offering, hours, status="active"):
    return LoadEntry(faculty, offering, hours, status)


def test_load_sums_active_hours_per_faculty_member():
    loads = faculty_load(
        [entry("f2", "o1", Decimal(4)), entry("f1", "o1", Decimal(6)), entry("f1", "o2", Decimal("4.5"))],
        max_weekly_contact_hours=18,
    )
    assert loads == [
        FacultyLoad("f1", 2, Decimal("10.5"), False),
        FacultyLoad("f2", 1, Decimal(4), False),
    ]


def test_two_assignments_on_one_offering_count_it_once():
    (load,) = faculty_load([entry("f1", "o1", Decimal(3)), entry("f1", "o1", Decimal(2))], max_weekly_contact_hours=18)
    assert (load.offerings_count, load.contact_hours) == (1, Decimal(5))


def test_ended_assignments_do_not_count():
    loads = faculty_load([entry("f1", "o1", Decimal(20), "ended"), entry("f1", "o2", 2)], max_weekly_contact_hours=18)
    assert loads == [FacultyLoad("f1", 1, Decimal(2), False)]


def test_only_ended_assignments_give_no_row():
    assert faculty_load([entry("f1", "o1", 4, "ended")], max_weekly_contact_hours=18) == []


@pytest.mark.parametrize(("hours", "over"), [(Decimal(18), False), (Decimal("18.5"), True), (Decimal(30), True)])
def test_over_the_maximum_is_flagged_not_refused(hours, over):
    (load,) = faculty_load([entry("f1", "o1", hours)], max_weekly_contact_hours=18)
    assert load.over_load is over


def test_exact_sums_of_fractional_hours():
    (load,) = faculty_load([entry("f1", "o1", 0.1), entry("f1", "o2", 0.2)], max_weekly_contact_hours=0.3)
    assert (load.contact_hours, load.over_load) == (Decimal("0.3"), False)


@pytest.mark.parametrize(
    ("entries", "maximum", "code", "field"),
    [
        ([], -1, "below_minimum", "max_weekly_contact_hours"),
        ([], "18", "invalid_number", "max_weekly_contact_hours"),
        ([entry("f1", "o1", -1)], 18, "below_minimum", "contact_hours"),
        ([entry("f1", "o1", 2, "paused")], 18, "invalid_choice", "status"),
    ],
)
def test_invalid_inputs_are_errors(entries, maximum, code, field):
    with pytest.raises(DomainRuleError) as err:
        faculty_load(entries, max_weekly_contact_hours=maximum)
    assert (err.value.code, err.value.field) == (code, field)
