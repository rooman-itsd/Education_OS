"""Unit tests of the term rules (domain layer): FR-1 non-overlapping dates, FR-2 one active term."""

from datetime import date, datetime

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.terms import (
    ACTIVE,
    CLOSED,
    UPCOMING,
    DateRange,
    Term,
    ensure_no_overlap,
    plan_activation,
)


def term(id_: str, start: date, end: date, status: str = UPCOMING) -> Term:
    return Term(id=id_, code=id_.upper(), name=id_, dates=DateRange(start, end), status=status)


ODD = term("t1", date(2026, 7, 1), date(2026, 11, 30), ACTIVE)
EVEN = term("t2", date(2026, 12, 1), date(2027, 4, 30))


def test_date_range_accepts_a_single_day():
    assert DateRange(date(2026, 7, 1), date(2026, 7, 1)).starts_on == date(2026, 7, 1)


def test_date_range_rejects_end_before_start():
    with pytest.raises(DomainRuleError) as err:
        DateRange(date(2026, 7, 2), date(2026, 7, 1))
    assert (err.value.code, err.value.kind, err.value.field) == ("invalid_term_dates", "invalid", "ends_on")


def test_adjacent_terms_do_not_overlap():
    ensure_no_overlap(DateRange(date(2027, 5, 1), date(2027, 6, 30)), [ODD, EVEN])


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 30), date(2026, 12, 15)),  # shares the last day of t1 (ranges are inclusive)
        (date(2026, 8, 1), date(2026, 9, 1)),  # inside t1
        (date(2026, 6, 1), date(2027, 6, 1)),  # covers both
    ],
)
def test_overlapping_dates_are_a_conflict(start, end):
    with pytest.raises(DomainRuleError) as err:
        ensure_no_overlap(DateRange(start, end), [ODD, EVEN])
    assert (err.value.code, err.value.kind) == ("term_dates_overlap", "conflict")


def test_overlap_names_every_clashing_term():
    with pytest.raises(DomainRuleError) as err:
        ensure_no_overlap(DateRange(date(2026, 6, 1), date(2027, 6, 1)), [EVEN, ODD])
    assert "T1, T2" in err.value.message


def test_a_term_does_not_overlap_itself_when_its_dates_change():
    ensure_no_overlap(DateRange(date(2026, 7, 15), date(2026, 11, 30)), [ODD, EVEN], ignore_id="t1")


def test_activation_closes_the_previously_active_term():
    plan = plan_activation([ODD, EVEN], "t2")
    assert plan.activated_id == "t2"
    assert plan.closed_ids == ("t1",)


def test_activation_with_no_active_term_closes_nothing():
    plan = plan_activation([term("t3", date(2028, 1, 1), date(2028, 6, 30))], "t3")
    assert plan.closed_ids == ()


def test_activating_the_active_term_changes_nothing():
    assert plan_activation([ODD, EVEN], "t1").closed_ids == ()


def test_activation_leaves_closed_terms_alone():
    old = term("t0", date(2026, 1, 1), date(2026, 6, 30), CLOSED)
    assert plan_activation([old, ODD, EVEN], "t2").closed_ids == ("t1",)


def test_activating_an_unknown_term_is_not_found():
    with pytest.raises(DomainRuleError) as err:
        plan_activation([ODD], "missing")
    assert (err.value.code, err.value.kind) == ("term_not_found", "not_found")


# --- regression: datetime inputs (D5)


@pytest.mark.parametrize(
    ("start", "end", "field"),
    [
        (datetime(2026, 7, 1, 9), datetime(2026, 7, 2, 9), "starts_on"),
        (date(2026, 7, 1), datetime(2026, 7, 2), "ends_on"),
        (datetime(2026, 7, 1), date(2026, 7, 2), "starts_on"),
        ("2026-07-01", date(2026, 7, 2), "starts_on"),
    ],
)
def test_date_range_accepts_only_plain_dates(start, end, field):
    with pytest.raises(DomainRuleError) as err:
        DateRange(start, end)
    assert (err.value.code, err.value.kind, err.value.field) == ("invalid_date", "invalid", field)


# --- regression: activation


def test_activation_closes_every_other_active_term():
    a = term("a", date(2025, 1, 1), date(2025, 6, 30), ACTIVE)
    b = term("b", date(2025, 7, 1), date(2025, 12, 31), ACTIVE)  # an inconsistent state the plan repairs
    c = term("c", date(2026, 1, 1), date(2026, 6, 30))
    plan = plan_activation([c, b, a], "c")
    assert (plan.activated_id, plan.closed_ids) == ("c", ("a", "b"))


def test_activating_one_of_two_active_terms_closes_only_the_other():
    a = term("a", date(2025, 1, 1), date(2025, 6, 30), ACTIVE)
    b = term("b", date(2025, 7, 1), date(2025, 12, 31), ACTIVE)
    assert plan_activation([a, b], "a").closed_ids == ("b",)


def test_activating_a_closed_term_is_not_refused_open_question():
    old = term("t0", date(2026, 1, 1), date(2026, 6, 30), CLOSED)
    assert plan_activation([old, ODD], "t0").closed_ids == ("t1",)


def test_a_term_with_an_unknown_status_cannot_exist():
    with pytest.raises(DomainRuleError) as err:
        term("x", date(2026, 1, 1), date(2026, 1, 2), "suspended")
    assert (err.value.code, err.value.field) == ("invalid_choice", "status")


# --- regression: which date an overlap is attributed to


@pytest.mark.parametrize(
    ("start", "end", "field"),
    [
        (date(2026, 11, 1), date(2026, 11, 30), "starts_on"),  # starts inside t1
        (date(2026, 6, 1), date(2026, 7, 1), "ends_on"),  # only the end reaches into t1
        (date(2026, 6, 1), date(2027, 5, 31), None),  # encloses both terms
    ],
)
def test_overlap_names_the_clashing_date(start, end, field):
    with pytest.raises(DomainRuleError) as err:
        ensure_no_overlap(DateRange(start, end), [ODD, EVEN])
    assert err.value.field == field
