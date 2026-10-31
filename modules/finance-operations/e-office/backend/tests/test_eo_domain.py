"""The pure rules: numbers, due dates, overdue, age buckets, and the settings that feed them."""

from datetime import UTC, date, datetime

import pytest
from eos_e_office.application import service
from eos_e_office.domain import rules
from eos_e_office.domain.rules import RuleError
from eos_e_office.infrastructure.config import load_settings

DAYS = {"normal": 7, "urgent": 2, "immediate": 1}


def test_numbers():
    assert rules.file_number("ADM", 2026, 7) == "ADM/2026/0007"
    assert rules.file_number("ADM", 2026, 12345) == "ADM/2026/12345"
    assert rules.register_number("IN", 2026, 12) == "IN/2026/00012"


@pytest.mark.parametrize("raw, code", [("adm", "ADM"), (" EST-01 ", "EST-01"), ("A1", "A1")])
def test_category_code_is_upper_cased(raw, code):
    assert rules.category_code(raw) == code


@pytest.mark.parametrize("raw", ["A", "AD M", "ADM/1", "X" * 21, ""])
def test_category_code_rejects_what_cannot_be_part_of_a_number(raw):
    with pytest.raises(RuleError) as e:
        rules.category_code(raw)
    assert e.value.code == "invalid_code" and e.value.field == "code"


def test_due_date_is_the_set_date_or_the_default_for_the_priority():
    received = date(2026, 10, 31)
    assert rules.due_date(date(2026, 11, 2), received, "normal", DAYS) == date(2026, 11, 2)
    assert rules.due_date(None, received, "normal", DAYS) == date(2026, 11, 7)
    assert rules.due_date(None, received, "urgent", DAYS) == date(2026, 11, 2)
    assert rules.due_date(None, received, "immediate", DAYS) == date(2026, 11, 1)


def test_overdue_from_the_day_after_the_due_date():
    due = date(2026, 11, 2)
    assert not rules.is_overdue(due, date(2026, 11, 2))
    assert rules.is_overdue(due, date(2026, 11, 3))


@pytest.mark.parametrize(
    "days, bucket", [(-1, "0-3d"), (0, "0-3d"), (3, "0-3d"), (4, "4-7d"), (8, "8-15d"), (30, "16-30d"), (31, "30d+")]
)
def test_age_buckets(days, bucket):
    assert rules.age_bucket(days) == bucket


def test_held_hours():
    assert rules.held_hours(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 1, 30, tzinfo=UTC)) == 1.5
    assert rules.held_hours(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)) == 0


def test_business_dates_are_indian():
    # 20:00 UTC on 31 October is 01:30 on 1 November in Asia/Kolkata
    assert service.business_date(datetime(2026, 10, 31, 20, 0, tzinfo=UTC)) == date(2026, 11, 1)
    assert service.business_date(datetime(2026, 10, 31, 18, 29)) == date(2026, 10, 31)  # naive means UTC


def test_default_due_days_come_from_the_environment(monkeypatch):
    assert load_settings().default_due_days == DAYS
    monkeypatch.setenv("E_OFFICE_DEFAULT_DUE_DAYS_NORMAL", "10")
    monkeypatch.setenv("E_OFFICE_DEFAULT_DUE_DAYS_URGENT", "three")  # unreadable: the default
    monkeypatch.setenv("E_OFFICE_DEFAULT_DUE_DAYS_IMMEDIATE", "-1")  # out of range: the default
    assert load_settings().default_due_days == {"normal": 10, "urgent": 2, "immediate": 1}
