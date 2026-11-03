"""Unit tests of the exam cycle rules (domain layer): FR-1, PRD 5.1 and the lifecycle of section 6."""

from datetime import date
from decimal import Decimal

import pytest
from conftest import uid
from eos_examinations.domain import cycles as cyc
from eos_examinations.domain.errors import DomainRuleError


def request(**over) -> dict:
    return {
        "academic_period_id": uid(),
        "code": "END-2026",
        "name": "End-term examinations",
        "cycle_type": "end_term",
        "starts_on": date(2026, 11, 20),
        "ends_on": date(2026, 12, 10),
        **over,
    }


def cycle(**over) -> cyc.Cycle:
    return cyc.new_cycle(uid(), request(**over), grading_scheme_id=uid())


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


def test_a_new_cycle_is_a_draft_with_the_contract_defaults():
    c = cycle()
    assert (c.status, c.check_dues, c.eligibility_cutoff_date, c.min_attendance_percent) == ("draft", False, None, None)
    assert (c.code, c.cycle_type, c.starts_on, c.ends_on) == (
        "END-2026",
        "end_term",
        date(2026, 11, 20),
        date(2026, 12, 10),
    )


def test_the_eligibility_rules_are_carried_when_given():
    c = cycle(eligibility_cutoff_date=date(2026, 11, 15), min_attendance_percent=75, check_dues=True)
    assert (c.eligibility_cutoff_date, c.min_attendance_percent, c.check_dues) == (
        date(2026, 11, 15),
        Decimal(75),
        True,
    )
    assert cycle(min_attendance_percent=0.5).min_attendance_percent == Decimal("0.5")


@pytest.mark.parametrize("cycle_type", ["internal", "mid_term", "end_term", "supplementary"])
def test_every_contract_cycle_type_is_accepted(cycle_type):
    assert cycle(cycle_type=cycle_type).cycle_type == cycle_type


@pytest.mark.parametrize(
    ("change", "expected", "field"),
    [
        ({"cycle_type": "annual"}, "invalid_choice", "cycle_type"),
        ({"code": "  "}, "invalid_text", "code"),
        ({"name": "x" * 201}, "text_too_long", "name"),
        ({"academic_period_id": "p"}, "invalid_id", "academic_period_id"),
        ({"starts_on": "2026-11-20"}, "invalid_date", "starts_on"),
        ({"ends_on": date(2026, 11, 19)}, "invalid_cycle_dates", "ends_on"),
        ({"min_attendance_percent": 101}, "above_maximum", "min_attendance_percent"),
        ({"min_attendance_percent": -1}, "below_minimum", "min_attendance_percent"),
        ({"min_attendance_percent": "75"}, "invalid_number", "min_attendance_percent"),
        ({"check_dues": "yes"}, "invalid_boolean", "check_dues"),
        ({"eligibility_cutoff_date": "soon"}, "invalid_date", "eligibility_cutoff_date"),
    ],
)
def test_invalid_cycles_are_refused_as_invalid_naming_the_field(change, expected, field):
    err = code(cycle, **change)
    assert (err.code, err.kind, err.field) == (expected, "invalid", field)


def test_a_one_day_cycle_is_valid():
    assert cycle(starts_on=date(2026, 12, 1), ends_on=date(2026, 12, 1)).ends_on == date(2026, 12, 1)


@pytest.mark.parametrize(
    ("status", "configurable"),
    [
        ("draft", True),
        ("scheduled", True),
        ("in_progress", False),
        ("evaluation", False),
        ("results_published", False),
        ("closed", False),
    ],
)
def test_a_cycle_can_be_configured_only_while_draft_or_scheduled(status, configurable):
    c = cyc.Cycle(**{**cycle().__dict__, "status": status})
    if configurable:
        cyc.ensure_configurable(c)
    else:
        err = code(cyc.ensure_configurable, c)
        assert (err.code, err.kind, err.details) == ("cycle_not_configurable", "conflict", {"status": status})


def test_the_lifecycle_moves_forward_one_status_at_a_time():
    c = cycle()
    seen = [c.status]
    for target in ("scheduled", "in_progress", "evaluation"):
        c = cyc.plan_status_change(c, target)
        seen.append(c.status)
    c = cyc.plan_status_change(c, "results_published", by_publication=True)
    c = cyc.plan_status_change(c, "closed")
    assert seen + [c.status] == ["draft", "scheduled", "in_progress", "evaluation", "closed"]


def test_results_published_is_set_by_publication_and_never_by_a_status_change():
    evaluating = cyc.Cycle(**{**cycle().__dict__, "status": "evaluation"})
    err = code(cyc.plan_status_change, evaluating, "results_published")
    assert (err.code, err.kind) == ("results_published_by_publication", "conflict")
    assert cyc.plan_status_change(evaluating, "results_published", by_publication=True).status == "results_published"


@pytest.mark.parametrize(
    ("status", "target"),
    [
        ("draft", "in_progress"),
        ("draft", "closed"),
        ("scheduled", "draft"),
        ("in_progress", "scheduled"),
        ("evaluation", "closed"),
    ],
)
def test_skipping_or_going_back_is_refused(status, target):
    c = cyc.Cycle(**{**cycle().__dict__, "status": status})
    err = code(cyc.plan_status_change, c, target)
    assert (err.code, err.kind) == ("invalid_status_transition", "conflict")
    assert err.details["from"] == status and err.details["to"] == target


def test_a_closed_cycle_cannot_change_status_and_an_unknown_status_is_invalid():
    closed = cyc.Cycle(**{**cycle().__dict__, "status": "closed"})
    assert code(cyc.plan_status_change, closed, "draft").details["allowed"] is None
    assert code(cyc.plan_status_change, cycle(), "archived").code == "invalid_choice"


def test_a_status_change_does_not_alter_the_original():
    c = cycle()
    assert cyc.plan_status_change(c, "scheduled").status == "scheduled"
    assert c.status == "draft"
