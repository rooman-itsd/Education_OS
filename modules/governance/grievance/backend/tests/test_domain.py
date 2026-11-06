"""Rules of a case, without a database or an HTTP client."""

from datetime import UTC, datetime, timedelta

import pytest
from eos_grievance.domain import cases as r
from eos_grievance.domain.errors import DomainRuleError

THURSDAY = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def test_every_track_has_one_committee_kind_and_back():
    assert {t: r.KIND_FOR_TRACK[t] for t in r.TRACKS} == {
        "student_grievance": "sgrc",
        "ragging": "anti_ragging",
        "sexual_harassment": "icc",
    }
    assert {r.TRACK_FOR_KIND[k] for k in r.TRACK_FOR_KIND} == set(r.TRACKS)
    assert "ombudsperson" not in r.TRACK_FOR_KIND
    assert r.committee_fits_track("sgrc", "student_grievance") and not r.committee_fits_track("icc", "ragging")
    assert not r.committee_fits_track("ombudsperson", "student_grievance")


def test_open_and_final_statuses_cover_every_status_once():
    assert set(r.OPEN_STATUSES) | set(r.FINAL_STATUSES) == set(r.STATUSES)
    assert not set(r.OPEN_STATUSES) & set(r.FINAL_STATUSES)


def test_status_moves():
    r.check_move("submitted", "acknowledged")
    r.check_move("decided", "closed")
    for status, target in (("acknowledged", "closed"), ("closed", "acknowledged"), ("under_inquiry", "decided")):
        with pytest.raises(DomainRuleError) as e:
            r.check_move(status, target)
        assert (e.value.code, e.value.kind) == ("invalid_status", "conflict")


def test_calendar_and_working_days():
    assert r.add_days(THURSDAY, 3, None) == THURSDAY + timedelta(days=3)
    assert r.add_days(THURSDAY, 3, "calendar") == THURSDAY + timedelta(days=3)
    assert r.add_days(THURSDAY, 2, "working") == THURSDAY + timedelta(days=4)  # Monday
    assert r.add_days(THURSDAY, 0, "working") == THURSDAY
    assert r.add_days(THURSDAY + timedelta(days=2), 1, "working") == THURSDAY + timedelta(days=4)  # from Saturday
    assert r.add_days(THURSDAY, r.MAX_DAYS, "working").year < 2200


def test_due_dates_follow_the_status():
    due = lambda status, ack, dec: r.due_at(status, THURSDAY, ack, dec, None)  # noqa: E731
    assert due("submitted", 2, 10) == THURSDAY + timedelta(days=2)
    assert due("submitted", None, 10) is None
    assert due("acknowledged", 2, 10) == THURSDAY + timedelta(days=10)
    assert due("under_inquiry", 2, None) is None
    for status in ("decided", "appealed", "appeal_decided", "closed", "withdrawn"):
        assert due(status, 2, 10) is None


def test_overdue_applies_to_open_cases_past_their_due_date():
    due = THURSDAY
    assert r.is_overdue("submitted", due, due + timedelta(seconds=1))
    assert not r.is_overdue("submitted", due, due)
    assert not r.is_overdue("closed", due, due + timedelta(days=9))
    assert not r.is_overdue("submitted", None, due + timedelta(days=9))


def test_the_appeal_window():
    assert r.appeal_open(THURSDAY, 7, None, THURSDAY + timedelta(days=7))
    assert not r.appeal_open(THURSDAY, 7, None, THURSDAY + timedelta(days=7, seconds=1))
    assert not r.appeal_open(THURSDAY, None, None, THURSDAY)
    assert not r.appeal_open(None, 7, None, THURSDAY)
