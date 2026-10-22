"""Unit tests of the faculty load rule (domain layer): FR-13 sum of contact hours, flagged over the maximum, and the
owner decisions on PR #168 (teaching assistants excluded, over-load first, counts independent of over_load_only)."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.load import FacultyLoad, LoadEntry, faculty_load, summarise


def entry(faculty, offering, hours, status="active", role="primary"):
    return LoadEntry(faculty, offering, role, hours, status)


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
        ([entry("f1", "o1", 2, role="lecturer")], 18, "invalid_choice", "role"),
    ],
)
def test_invalid_inputs_are_errors(entries, maximum, code, field):
    with pytest.raises(DomainRuleError) as err:
        faculty_load(entries, max_weekly_contact_hours=maximum)
    assert (err.value.code, err.value.field) == (code, field)


# --- owner decisions on PR #168


def test_teaching_assistant_hours_do_not_count():
    (load,) = faculty_load(
        [entry("f1", "o1", Decimal(4)), entry("f1", "o2", Decimal(6), role="teaching_assistant")],
        max_weekly_contact_hours=18,
    )
    assert (load.offerings_count, load.contact_hours) == (1, Decimal(4))


def test_co_instructor_hours_count():
    (load,) = faculty_load([entry("f1", "o1", Decimal(3), role="co_instructor")], max_weekly_contact_hours=18)
    assert load.contact_hours == Decimal(3)


def test_faculty_with_only_teaching_assistant_assignments_are_not_listed():
    assert faculty_load([entry("f1", "o1", Decimal(30), role="teaching_assistant")], max_weekly_contact_hours=18) == []


def test_over_load_first_then_contact_hours_descending():
    loads = faculty_load(
        [
            entry("a", "o1", Decimal(5)),
            entry("b", "o1", Decimal(20)),
            entry("c", "o1", Decimal(12)),
            entry("d", "o1", Decimal(25)),
            entry("e", "o1", Decimal(12)),
        ],
        max_weekly_contact_hours=18,
    )
    assert [(load.faculty_id, load.over_load) for load in loads] == [
        ("d", True),
        ("b", True),
        ("c", False),  # equal hours: faculty_id keeps the order stable
        ("e", False),
        ("a", False),
    ]


def test_summary_counts_stay_the_same_when_only_over_load_rows_are_kept():
    loads = faculty_load(
        [entry("a", "o1", Decimal(5)), entry("b", "o1", Decimal(20)), entry("c", "o2", Decimal(19))],
        max_weekly_contact_hours=18,
    )
    every = summarise(loads)
    over = summarise(loads, over_load_only=True)
    assert [load.faculty_id for load in every.items] == ["b", "c", "a"]
    assert [load.faculty_id for load in over.items] == ["b", "c"]
    assert (every.faculty_count, every.over_load_count) == (over.faculty_count, over.over_load_count) == (3, 2)


def test_summary_of_no_load_is_empty():
    summary = summarise([], over_load_only=True)
    assert (summary.items, summary.faculty_count, summary.over_load_count) == ((), 0, 0)
