"""The pure rules: record values, the no-future-dates rule (A7) and session values."""

from datetime import UTC, date, datetime

import pytest
from eos_alumni.application import service
from eos_alumni.domain import rules
from eos_alumni.domain.rules import RuleError

TODAY = date(2026, 11, 3)


def _code(fn, *args) -> str:
    with pytest.raises(RuleError) as e:
        fn(*args)
    return e.value.code


def test_full_name_is_trimmed_and_limited():
    assert rules.full_name("  Ananya Rao ") == "Ananya Rao"
    assert rules.full_name("x" * 200) == "x" * 200
    for bad in ("", "   ", None, "x" * 201):
        assert _code(rules.full_name, bad) == "invalid_name"


def test_graduation_year_is_from_1900_to_this_year():
    assert rules.graduation_year(1900, 2026) == 1900
    assert rules.graduation_year(2026, 2026) == 2026
    for bad in (1899, 2027, True):
        assert _code(rules.graduation_year, bad, 2026) == "invalid_graduation_year"


def test_contact_details():
    assert rules.email(" a.b@example.co.in ") == "a.b@example.co.in"
    assert rules.email("") is None and rules.email(None) is None
    for bad in ("not-an-email", "a@b", "a b@example.com", "x" * 190 + "@example.com"):
        assert _code(rules.email, bad) == "invalid_email"
    for good in ("+91 98450 12345", "080-2345 6789", "(080) 23456789", "9845012345"):
        assert rules.phone(good) == good
    for bad in ("12345", "phone me", "+91 98450 12345 12345 1", "98450#12345"):
        assert _code(rules.phone, bad) == "invalid_phone"
    assert rules.url("https://www.linkedin.com/in/x") == "https://www.linkedin.com/in/x"
    assert rules.url("  ") is None
    for bad in (
        "linkedin.com/in/x",
        "ftp://x.example.com",
        "https://",
        "https://x.com/" + "a" * 200,
        "https://a b.com",
    ):
        assert _code(rules.url, bad) == "invalid_url"


def test_started_on_is_today_or_earlier():
    assert rules.started_on(None, TODAY) == TODAY
    assert rules.started_on(date(2026, 1, 1), TODAY) == date(2026, 1, 1)
    assert _code(rules.started_on, date(2026, 11, 4), TODAY) == "invalid_date"


def test_ended_on_is_between_started_on_and_today():
    start = date(2026, 10, 1)
    assert rules.ended_on(None, start, TODAY) == TODAY
    assert rules.ended_on(start, start, TODAY) == start
    assert _code(rules.ended_on, date(2026, 9, 30), start, TODAY) == "invalid_date"
    assert _code(rules.ended_on, date(2026, 11, 4), start, TODAY) == "invalid_date"


def test_a_session_is_not_before_its_assignment_started_in_india():
    start = date(2026, 11, 3)
    # 19:00 UTC on 2 November is 00:30 on 3 November in Asia/Kolkata: allowed
    assert rules.scheduled_at(datetime(2026, 11, 2, 19, 0, tzinfo=UTC), start, service.business_date)
    # 18:00 UTC on 2 November is 23:30 on 2 November in Asia/Kolkata: before the start
    with pytest.raises(RuleError) as e:
        rules.scheduled_at(datetime(2026, 11, 2, 18, 0, tzinfo=UTC), start, service.business_date)
    assert e.value.code == "invalid_scheduled_at"
    naive = rules.scheduled_at(datetime(2026, 11, 5, 10, 0), start, service.business_date)
    assert naive.tzinfo is UTC  # a time without an offset is UTC


def test_duration_is_1_to_480_minutes():
    assert rules.duration(None) is None and rules.duration(1) == 1 and rules.duration(480) == 480
    for bad in (0, 481, -5, True):
        assert _code(rules.duration, bad) == "invalid_duration"


def test_business_date_is_the_asia_kolkata_date():
    assert service.business_date(datetime(2026, 11, 3, 18, 29, tzinfo=UTC)) == date(2026, 11, 3)
    assert service.business_date(datetime(2026, 11, 3, 18, 30, tzinfo=UTC)) == date(2026, 11, 4)
