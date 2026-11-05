"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime

import pytest
from eos_transport.domain import rules
from eos_transport.domain.rules import PASS_TRANSITIONS, RuleViolationError

TODAY = date(2026, 10, 27)


def code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_pass_transitions():
    assert rules.transition(PASS_TRANSITIONS, "issue", "requested") == "issued"
    assert rules.transition(PASS_TRANSITIONS, "reject", "requested") == "rejected"
    assert rules.transition(PASS_TRANSITIONS, "cancel", "requested") == "cancelled"
    assert rules.transition(PASS_TRANSITIONS, "cancel", "issued") == "cancelled"
    assert rules.transition(PASS_TRANSITIONS, "expire", "issued") == "expired"
    for action, status in (
        ("issue", "issued"),
        ("cancel", "cancelled"),
        ("cancel", "expired"),
        ("expire", "requested"),
    ):
        assert code(rules.transition, PASS_TRANSITIONS, action, status) == "invalid_status"


def test_route_stops_are_ordered_and_unique():
    a, b, c = "a", "b", "c"
    ordered = rules.check_route_stops([{"stop_id": b, "sequence": 2}, {"stop_id": a, "sequence": 1}])
    assert [s["stop_id"] for s in ordered] == [a, b]
    assert code(rules.check_route_stops, [{"stop_id": a, "sequence": 1}]) == "invalid_stops"
    assert (
        code(rules.check_route_stops, [{"stop_id": a, "sequence": 1}, {"stop_id": a, "sequence": 2}]) == "invalid_stops"
    )
    assert (
        code(rules.check_route_stops, [{"stop_id": a, "sequence": 1}, {"stop_id": c, "sequence": 1}]) == "invalid_stops"
    )


def test_document_expiry():
    assert not rules.is_expired(None, TODAY)
    assert not rules.is_expired(TODAY, TODAY)  # valid through its expiry day
    assert rules.is_expired(date(2026, 10, 26), TODAY)
    assert rules.expires_within(date(2026, 11, 26), TODAY, 30)
    assert not rules.expires_within(date(2026, 11, 27), TODAY, 30)
    assert rules.expires_within(date(2026, 1, 1), TODAY, 30)  # already expired counts
    assert not rules.expires_within(None, TODAY, 30)


def test_assignable():
    good = {"insurance": date(2027, 1, 1), "fitness": date(2027, 1, 1), "permit": date(2026, 1, 1)}
    rules.check_assignable(True, good, True, date(2027, 1, 1), TODAY)  # an expired permit does not block
    assert code(rules.check_assignable, False, good, True, date(2027, 1, 1), TODAY) == "vehicle_inactive"
    assert code(rules.check_assignable, True, good, False, date(2027, 1, 1), TODAY) == "driver_inactive"
    for doc in ("insurance", "fitness"):
        assert code(rules.check_assignable, True, {**good, doc: date(2026, 10, 1)}, True, date(2027, 1, 1), TODAY) == (
            "document_expired"
        )
    assert code(rules.check_assignable, True, good, True, date(2026, 10, 1), TODAY) == "document_expired"


def test_pass_period_and_overlap():
    rules.check_pass_period(TODAY, TODAY, TODAY)
    assert code(rules.check_pass_period, TODAY, date(2026, 10, 1), TODAY) == "invalid_dates"
    assert code(rules.check_pass_period, date(2026, 9, 1), date(2026, 10, 1), TODAY) == "invalid_dates"
    assert rules.periods_overlap(date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 31), date(2026, 2, 28))
    assert not rules.periods_overlap(date(2026, 1, 1), date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 28))


def test_capacity():
    rules.check_capacity(2, 1, False, None)
    assert code(rules.check_capacity, 2, 2, False, None) == "route_full"
    assert code(rules.check_capacity, None, 0, False, None) == "route_full"  # no vehicle, no seats
    assert code(rules.check_capacity, 2, 2, True, "  ") == "reason_required"
    rules.check_capacity(2, 2, True, "Exam week extra rider")
    rules.check_capacity(None, 0, True, "Van arrives Monday")


def test_pass_covers():
    assert rules.pass_covers("issued", TODAY, TODAY, TODAY)
    assert not rules.pass_covers("requested", TODAY, TODAY, TODAY)
    assert not rules.pass_covers("issued", date(2026, 11, 1), date(2026, 12, 1), TODAY)


def test_nearest_stop():
    stops = [("a", 12.90, 77.6), ("b", 12.95, 77.6), ("c", None, None)]
    assert rules.nearest_stop((12.94, 77.6), stops) == "b"
    assert rules.nearest_stop((12.80, 77.6), stops) == "a"
    assert rules.nearest_stop(None, stops) is None
    assert rules.nearest_stop((12.9, 77.6), [("c", None, None)]) is None
    assert round(rules.distance_km(12.9, 77.6, 13.0, 77.6), 1) == 11.1


def test_notices():
    now = datetime(2026, 10, 27, 8, tzinfo=UTC)
    later = datetime(2026, 10, 27, 9, tzinfo=UTC)
    assert rules.notice_status(None, None, now) == "current"
    assert rules.notice_status(None, later, now) == "current"
    assert rules.notice_status(None, now, now) == "expired"
    assert rules.notice_status(now, later, now) == "withdrawn"
    assert rules.notice_visible_to(None, set())
    assert rules.notice_visible_to("r1", {"r1"})
    assert not rules.notice_visible_to("r2", {"r1"})
