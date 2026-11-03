"""Unit tests of scheduled-class rules (domain layer): FR-3 unpublishing, FR-5 generation, rescheduling, cancelling."""

import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone

import pytest
from eos_timetable_attendance.domain.classes import (
    CANCELLED,
    COMPLETED,
    SCHEDULED,
    ScheduledClass,
    classes_to_cancel_on_unpublish,
    missing_occurrences,
    new_adhoc_window,
    occurrence_window,
    plan_cancel,
    plan_reschedule,
    slot_dates,
)
from eos_timetable_attendance.domain.errors import DomainRuleError
from eos_timetable_attendance.domain.timetables import Slot

IST = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)  # Monday 09:30 IST


def uid() -> str:
    return str(uuid.uuid4())


def slot(**over) -> Slot:
    base = {
        "id": uid(),
        "day_of_week": "monday",
        "start_time": time(9, 30),
        "end_time": time(10, 30),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
    }
    return Slot(**{**base, **over})


def klass(**over) -> ScheduledClass:
    base = {
        "id": uid(),
        "academic_period_id": uid(),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
        "instructor_id": uid(),
        "class_date": date(2026, 11, 9),
        "starts_at": START,
        "ends_at": START + timedelta(hours=1),
        "slot_id": uid(),
    }
    return ScheduledClass(**{**base, **over})


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


def test_slot_dates_are_the_slots_weekday_inside_the_range():
    mondays = list(slot_dates(slot(), date(2026, 11, 1), date(2026, 11, 30)))
    assert mondays == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16), date(2026, 11, 23), date(2026, 11, 30)]


def test_slot_dates_respect_the_effective_dates_and_include_both_ends():
    s = slot(effective_from=date(2026, 11, 9), effective_to=date(2026, 11, 23))
    assert list(slot_dates(s, date(2026, 11, 1), date(2026, 11, 30))) == [
        date(2026, 11, 9),
        date(2026, 11, 16),
        date(2026, 11, 23),
    ]
    assert list(slot_dates(slot(), date(2026, 11, 9), date(2026, 11, 9))) == [date(2026, 11, 9)]
    assert list(slot_dates(slot(day_of_week="tuesday"), date(2026, 11, 9), date(2026, 11, 9))) == []


def test_slot_dates_reject_a_backwards_range_and_datetimes():
    assert code(lambda: list(slot_dates(slot(), date(2026, 11, 9), date(2026, 11, 8)))).code == "invalid_range"
    assert code(lambda: list(slot_dates(slot(), datetime(2026, 11, 9), date(2026, 11, 9)))).code == "invalid_date"


def test_generation_is_idempotent_and_a_cancelled_date_stays_taken():
    s = slot()
    first = missing_occurrences(s, date(2026, 11, 1), date(2026, 11, 16), [])
    assert first == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]
    assert missing_occurrences(s, date(2026, 11, 1), date(2026, 11, 16), first) == []
    assert missing_occurrences(s, date(2026, 11, 1), date(2026, 11, 16), [date(2026, 11, 9)]) == [
        date(2026, 11, 2),
        date(2026, 11, 16),
    ]


def test_occurrence_window_reads_the_slot_in_the_organisation_zone():
    start, end = occurrence_window(date(2026, 11, 9), slot(), IST)
    assert (start, end) == (START, START + timedelta(hours=1))
    assert start.tzinfo == UTC


def test_adhoc_window_needs_zones_and_a_positive_length():
    assert new_adhoc_window(START.astimezone(IST), START + timedelta(hours=1)) == (START, START + timedelta(hours=1))
    assert code(new_adhoc_window, START, START).code == "invalid_class_times"
    assert code(new_adhoc_window, datetime(2026, 11, 9, 9), START).code == "invalid_datetime"
    assert code(new_adhoc_window, "2026-11-09", START).field == "starts_at"


def test_a_class_must_end_after_it_starts_and_use_a_known_status():
    assert code(klass, ends_at=START).code == "invalid_class_times"
    assert code(klass, status="gone").code == "invalid_choice"
    assert klass(slot_id=None).is_adhoc and not klass().is_adhoc


def test_reschedule_moves_the_class_and_reports_the_changed_fields():
    cls = klass()
    moved, changed = plan_reschedule(
        cls,
        has_closed_session=False,
        starts_at=START + timedelta(days=1),
        ends_at=START + timedelta(days=1, hours=1),
        zone=IST,
    )
    assert changed == ["starts_at", "ends_at"]
    assert (moved.id, moved.class_date, moved.status) == (cls.id, date(2026, 11, 10), SCHEDULED)


def test_class_date_follows_the_start_in_the_organisation_zone():
    late = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)  # 01:30 on the 10th in IST
    moved, _ = plan_reschedule(
        klass(), has_closed_session=False, starts_at=late, ends_at=late + timedelta(hours=1), zone=IST
    )
    assert moved.class_date == date(2026, 11, 10)


def test_reschedule_can_change_location_and_instructor_and_clear_the_location():
    cls = klass(location_label="Room 1")
    new_assignment, new_teacher = uid(), uid()
    moved, changed = plan_reschedule(
        cls, has_closed_session=False, location_label=" Room 2 ", instructor=(new_assignment, new_teacher)
    )
    assert changed == ["location_label", "instructor_assignment_id"]
    assert (moved.location_label, moved.instructor_assignment_id, moved.instructor_id) == (
        "Room 2",
        new_assignment,
        new_teacher,
    )
    assert plan_reschedule(cls, has_closed_session=False, location_label=None)[0].location_label is None


def test_reschedule_that_changes_nothing_reports_no_fields():
    cls = klass(location_label="Room 1")
    same, changed = plan_reschedule(
        cls,
        has_closed_session=False,
        starts_at=cls.starts_at,
        location_label="Room 1",
        instructor=(cls.instructor_assignment_id, cls.instructor_id),
    )
    assert (same, changed) == (cls, [])


def test_reschedule_checks_the_new_times():
    assert code(plan_reschedule, klass(), has_closed_session=False, ends_at=START).code == "invalid_class_times"
    assert (
        code(plan_reschedule, klass(), has_closed_session=False, starts_at=START + timedelta(hours=2)).field
        == "ends_at"
    )


@pytest.mark.parametrize(
    ("cls", "closed", "expected"),
    [
        (klass(status=CANCELLED), False, "class_cancelled"),
        (klass(status=COMPLETED), False, "attendance_closed"),
        (klass(), True, "attendance_closed"),
    ],
)
def test_a_cancelled_completed_or_closed_class_cannot_change(cls, closed, expected):
    for action in (plan_reschedule, plan_cancel):
        err = code(action, cls, has_closed_session=closed)
        assert (err.code, err.kind) == (expected, "conflict")


def test_cancel_keeps_the_trimmed_reason():
    done = plan_cancel(klass(), has_closed_session=False, reason="  Strike  ")
    assert (done.status, done.cancel_reason) == (CANCELLED, "Strike")
    assert plan_cancel(klass(), has_closed_session=False).cancel_reason is None
    assert code(plan_cancel, klass(), has_closed_session=False, reason="  ").code == "invalid_text"


def test_unpublishing_cancels_only_future_scheduled_classes_without_a_session():
    now = START
    future, with_session = (
        klass(starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1)),
        klass(starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=1)),
    )
    started = klass(starts_at=now - timedelta(minutes=1), ends_at=now + timedelta(hours=1))
    past = klass(starts_at=now - timedelta(days=1), ends_at=now - timedelta(days=1) + timedelta(hours=1))
    cancelled = klass(status=CANCELLED, starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=3, hours=1))
    chosen = classes_to_cancel_on_unpublish([future, with_session, started, past, cancelled], [with_session.id], now)
    assert chosen == [future]
    assert code(classes_to_cancel_on_unpublish, [], [], datetime(2026, 11, 9)).code == "invalid_datetime"
