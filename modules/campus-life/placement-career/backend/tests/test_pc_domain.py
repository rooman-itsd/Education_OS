"""The pure rules: the fixed application sequence, field values, eligibility and declarations, and the date rules."""

from datetime import date
from decimal import Decimal

import pytest
from eos_placement_career.domain import rules
from eos_placement_career.domain.rules import RuleError

TODAY = date(2026, 11, 3)


def _code(fn, *args):
    with pytest.raises(RuleError) as e:
        fn(*args)
    return e.value.code, e.value.kind


def test_the_sequence_is_one_step_at_a_time():
    path = ["applied", "shortlisted", "in_process", "offered", "accepted"]
    for current, target in zip(path, path[1:], strict=False):
        assert rules.step(current, target) == target
    assert rules.step("offered", "declined") == "declined"
    for current in ("applied", "shortlisted", "in_process"):
        assert rules.step(current, "rejected") == "rejected"
    for status in rules.APPLICATION_STATUSES:
        for target in rules.STEPS:
            allowed = target in rules.NEXT.get(status, ()) or (target == "rejected" and status in rules.ENDABLE)
            if not allowed:
                assert _code(rules.step, status, target) == ("invalid_transition", "conflict"), (status, target)


def test_nothing_leaves_a_final_status():
    for status in rules.FINAL:
        assert status not in rules.NEXT and not rules.withdrawable(status)


@pytest.mark.parametrize("target", ["applied", "withdrawn", "hired", None])
def test_only_officer_steps_are_statuses(target):
    assert _code(rules.step, "applied", target) == ("invalid_status", "invalid")


def test_withdraw_before_an_offer_only():
    assert [s for s in rules.APPLICATION_STATUSES if rules.withdrawable(s)] == ["applied", "shortlisted", "in_process"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", Decimal("0.00")), ("650000", Decimal("650000.00")), ("12.5", Decimal("12.50")), (None, None)],
)
def test_money(raw, expected):
    assert rules.money(raw) == expected


@pytest.mark.parametrize("raw", ["-1", "1.234", "1e5", "", " ", "abc", 100, 1.5, "1" * 13])
def test_bad_money(raw):
    assert _code(rules.money, raw) == ("invalid_amount", "invalid")


def test_money_text_has_two_decimals():
    assert rules.money_text(Decimal("5")) == "5.00" and rules.money_text(None) is None


def test_names_titles_urls_and_emails():
    assert rules.company_name("  Acme  ") == "Acme"
    assert rules.name_key(" Acme   Systems ") == rules.name_key("acme systems")
    assert _code(rules.company_name, "") == ("invalid_name", "invalid")
    assert _code(rules.title, None) == ("invalid_title", "invalid")
    assert rules.website("https://a.example/careers") == "https://a.example/careers" and rules.website(" ") is None
    for bad in ("a.example", "mailto:x@a.example", "http://", "https://a b.example"):
        assert _code(rules.website, bad) == ("invalid_url", "invalid"), bad
    assert rules.email("hr@a.example") == "hr@a.example" and rules.email("") is None
    for bad in ("hr", "hr@a", "h r@a.example"):
        assert _code(rules.email, bad) == ("invalid_email", "invalid"), bad


def test_positions():
    assert rules.positions(None) is None and rules.positions(1) == 1
    assert _code(rules.positions, 0) == ("invalid_positions", "invalid")


def test_eligibility_is_normalised_and_ranged():
    assert rules.eligibility(None) == {
        "programmes": [],
        "graduating_years": [],
        "min_cgpa": None,
        "max_active_backlogs": None,
        "notes": None,
    }
    got = rules.eligibility({"programmes": [" MBA "], "min_cgpa": 0, "max_active_backlogs": 0, "notes": " "})
    assert got["programmes"] == ["MBA"] and got["min_cgpa"] == 0.0 and got["notes"] is None
    for bad in ({"min_cgpa": 10.01}, {"min_cgpa": -0.1}, {"max_active_backlogs": -1}, {"programmes": [""]}):
        assert _code(rules.eligibility, bad) == ("invalid_eligibility", "invalid"), bad


def test_declaration_is_ranged_not_checked():
    assert rules.declaration({"programme": " ", "cgpa": 10, "active_backlogs": 3}) == {
        "programme": None,
        "graduating_year": None,
        "cgpa": 10.0,
        "active_backlogs": 3,
    }
    for bad in ({"cgpa": 10.5}, {"active_backlogs": -1}):
        assert _code(rules.declaration, bad) == ("invalid_eligibility", "invalid"), bad


def test_dates():
    assert rules.not_before(TODAY, TODAY, "x") == TODAY and rules.not_before(None, TODAY, "x") is None
    assert _code(rules.not_before, date(2026, 11, 2), TODAY, "x") == ("invalid_date", "invalid")
    rules.drive_dates(TODAY, TODAY, TODAY)
    assert _code(rules.drive_dates, TODAY, date(2026, 11, 2), None) == ("invalid_date", "invalid")
    assert _code(rules.drive_dates, TODAY, None, date(2026, 11, 4)) == ("invalid_date", "invalid")
    rules.within_drive(TODAY, TODAY)
    assert _code(rules.within_drive, date(2026, 11, 4), TODAY) == ("close_date_after_drive", "invalid")
