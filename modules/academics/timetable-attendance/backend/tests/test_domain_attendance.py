"""Unit tests of attendance rules (domain layer): FR-7 to FR-11."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from eos_timetable_attendance.domain.attendance import (
    CLOSED,
    DEPARTMENT,
    INSTRUCTOR,
    OPEN,
    ORGANISATION,
    Mark,
    Policy,
    Session,
    counts,
    ensure_can_mark,
    ensure_can_open,
    ensure_eligible,
    is_due_for_auto_close,
    marking_window,
    parse_marks,
    plan_close,
    plan_correction,
)
from eos_timetable_attendance.domain.classes import CANCELLED, COMPLETED, ScheduledClass
from eos_timetable_attendance.domain.errors import DomainRuleError

STARTS = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)
ENDS = STARTS + timedelta(hours=1)
POLICY = Policy()  # 15 minutes before, 24 hours after, 7 days to correct, 75 percent


def uid() -> str:
    return str(uuid.uuid4())


def klass(**over) -> ScheduledClass:
    base = {
        "id": uid(),
        "academic_period_id": uid(),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
        "instructor_id": uid(),
        "class_date": STARTS.date(),
        "starts_at": STARTS,
        "ends_at": ENDS,
    }
    return ScheduledClass(**{**base, **over})


def session(cls: ScheduledClass | None = None, **over) -> Session:
    cls = cls or klass()
    base = {
        "id": uid(),
        "scheduled_class_id": cls.id,
        "opened_at": STARTS,
        "opened_by": uid(),
        "marking_deadline": marking_window(cls, POLICY).closes_at,
    }
    return Session(**{**base, **over})


def closed_session(at: datetime = ENDS, by: str | None = None) -> Session:
    return session(status=CLOSED, closed_at=at, closed_by=by)


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


def test_policy_rejects_negative_windows_and_thresholds_outside_0_to_100():
    assert code(Policy, marking_window_hours=-1).field == "marking_window_hours"
    assert code(Policy, correction_window_days=True).code == "invalid_policy"
    assert code(Policy, shortage_threshold_percent=101).field == "shortage_threshold_percent"
    assert Policy(0, 0, 0, 0).marking_window_hours == 0


def test_marking_window_runs_from_before_the_start_to_after_the_end():
    w = marking_window(klass(), POLICY)
    assert (w.opens_at, w.closes_at) == (STARTS - timedelta(minutes=15), ENDS + timedelta(hours=24))
    assert w.contains(w.opens_at) and w.contains(w.closes_at)
    assert not w.contains(w.opens_at - timedelta(seconds=1)) and not w.contains(w.closes_at + timedelta(seconds=1))


def test_a_new_session_may_open_inside_the_window():
    assert ensure_can_open(klass(), None, STARTS - timedelta(minutes=15), POLICY) is None
    assert ensure_can_open(klass(), None, ENDS + timedelta(hours=24), POLICY) is None


def test_opening_outside_the_window_is_a_conflict_with_the_window_bounds():
    err = code(ensure_can_open, klass(), None, STARTS - timedelta(minutes=16), POLICY)
    assert (err.code, err.kind) == ("outside_marking_window", "conflict")
    assert err.details["opens_at"] == (STARTS - timedelta(minutes=15)).isoformat()
    assert code(ensure_can_open, klass(), None, ENDS + timedelta(hours=24, seconds=1), POLICY).kind == "conflict"


def test_opening_twice_returns_the_open_session_even_outside_the_window():
    cls = klass()
    open_one = session(cls)
    assert ensure_can_open(cls, open_one, ENDS + timedelta(days=30), POLICY) is open_one


@pytest.mark.parametrize(("status", "expected"), [(CANCELLED, "class_cancelled"), (COMPLETED, "class_completed")])
def test_a_class_that_is_not_scheduled_cannot_open(status, expected):
    assert code(ensure_can_open, klass(status=status), None, STARTS, POLICY).code == expected


def test_a_closed_session_cannot_be_opened_again():
    cls = klass()
    assert (
        code(ensure_can_open, cls, session(cls, status=CLOSED, closed_at=ENDS), STARTS, POLICY).code == "session_closed"
    )


def test_a_closed_session_is_reported_even_though_closing_completed_the_class():
    cls = klass(status=COMPLETED)
    err = code(ensure_can_open, cls, session(cls, status=CLOSED, closed_at=ENDS), STARTS, POLICY)
    assert (err.code, err.kind) == ("session_closed", "conflict")


def test_marking_needs_an_open_session_before_the_deadline():
    s = session()
    ensure_can_mark(s, s.marking_deadline)
    err = code(ensure_can_mark, s, s.marking_deadline + timedelta(seconds=1))
    assert (err.code, err.kind) == ("marking_window_ended", "conflict")
    err = code(ensure_can_mark, closed_session(), STARTS)
    assert (err.code, err.kind) == ("session_closed", "conflict")


def test_due_for_auto_close_only_when_open_and_past_the_deadline():
    s = session()
    assert not is_due_for_auto_close(s, s.marking_deadline)
    assert is_due_for_auto_close(s, s.marking_deadline + timedelta(seconds=1))
    assert not is_due_for_auto_close(closed_session(), s.marking_deadline + timedelta(days=9))


def test_session_closed_at_must_match_its_status():
    assert (
        code(
            Session,
            id=uid(),
            scheduled_class_id=uid(),
            opened_at=STARTS,
            opened_by=uid(),
            marking_deadline=ENDS,
            status=CLOSED,
        ).code
        == "invalid_session"
    )
    assert (
        code(
            Session,
            id=uid(),
            scheduled_class_id=uid(),
            opened_at=STARTS,
            opened_by=uid(),
            marking_deadline=ENDS,
            closed_at=ENDS,
        ).code
        == "invalid_session"
    )


def test_parse_marks_reads_students_statuses_and_trimmed_remarks():
    a, b = uid(), uid()
    marks = parse_marks(
        [{"student_id": a, "status": "present"}, {"student_id": b, "status": "late", "remark": "  bus  "}]
    )
    assert marks == [Mark(a, "present", None), Mark(b, "late", "bus")]
    assert parse_marks([{"student_id": a, "status": "absent", "remark": "  "}])[0].remark is None


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([], "no_records"),
        (None, "no_records"),
        (["x"], "invalid_record"),
        ([{"student_id": "nope", "status": "present"}], "invalid_id"),
        ([{"student_id": str(uuid.uuid4()), "status": "asleep"}], "invalid_choice"),
        ([{"student_id": str(uuid.uuid4()), "status": "present", "remark": 5}], "invalid_text"),
        ([{"student_id": str(uuid.uuid4()), "status": "present", "remark": "x" * 501}], "text_too_long"),
    ],
)
def test_parse_marks_rejects_bad_input_as_invalid(items, expected):
    err = code(parse_marks, items)
    assert (err.code, err.kind) == (expected, "invalid")


def test_parse_marks_refuses_a_student_twice():
    a = uid()
    err = code(parse_marks, [{"student_id": a, "status": "present"}, {"student_id": a, "status": "absent"}])
    assert (err.code, err.details) == ("duplicate_student", {"student_id": a})


def test_only_eligible_students_can_be_marked():
    a, b, c = uid(), uid(), uid()
    ensure_eligible([Mark(a, "present")], [a, b])
    err = code(ensure_eligible, [Mark(a, "present"), Mark(c, "absent")], [a, b])
    assert (err.code, err.kind, err.details) == ("student_not_eligible", "unprocessable", {"student_ids": [c]})


def test_counts_cover_every_status_and_the_unmarked():
    a, b, c, d = (uid() for _ in range(4))
    got = counts([a, b, c, d], {a: "present", b: "late", c: "absent", uid(): "present"})
    assert got == {"eligible": 4, "unmarked": 1, "present": 1, "absent": 1, "late": 1, "excused": 0}
    assert counts([a, a], {}) == {"eligible": 1, "unmarked": 1, "present": 0, "absent": 0, "late": 0, "excused": 0}


def test_closing_makes_the_unmarked_absent_and_records_who_closed():
    a, b, c = uid(), uid(), uid()
    s, user = session(), uid()
    closed, absent = plan_close(s, [a, b, c], {a: "present"}, now=ENDS, closed_by=user)
    assert (closed.status, closed.closed_at, closed.closed_by) == (CLOSED, ENDS, user)
    assert absent == [b, c]
    system, _ = plan_close(s, [a], {}, now=ENDS, closed_by=None)
    assert system.closed_by is None and system.closed_at == ENDS
    assert (s.status, s.closed_at) == (OPEN, None)  # the original is untouched


def test_closing_a_closed_session_is_a_conflict():
    err = code(plan_close, closed_session(), [], {}, now=ENDS, closed_by=None)
    assert (err.code, err.kind) == ("session_closed", "conflict")


def test_correction_needs_a_closed_session_and_a_reason():
    open_err = code(
        plan_correction, session(), "absent", "present", "late bus", None, scope=INSTRUCTOR, now=ENDS, policy=POLICY
    )
    assert (open_err.code, open_err.kind) == ("session_open", "conflict")
    assert (
        code(
            plan_correction,
            closed_session(),
            "absent",
            "present",
            "  ",
            None,
            scope=INSTRUCTOR,
            now=ENDS,
            policy=POLICY,
        ).field
        == "reason"
    )
    assert (
        code(
            plan_correction,
            closed_session(),
            "absent",
            "present",
            None,
            None,
            scope=INSTRUCTOR,
            now=ENDS,
            policy=POLICY,
        ).code
        == "invalid_text"
    )


def test_correction_keeps_the_old_value_and_the_trimmed_reason():
    c = plan_correction(
        closed_session(), "absent", "present", "  Was on duty ", " note ", scope=INSTRUCTOR, now=ENDS, policy=POLICY
    )
    assert (c.from_status, c.to_status, c.reason, c.remark) == ("absent", "present", "Was on duty", "note")


def test_the_instructor_corrects_only_within_the_window_but_wider_scopes_always_can():
    closed = closed_session(ENDS)
    edge = ENDS + timedelta(days=7)
    plan_correction(closed, "absent", "present", "r", None, scope=INSTRUCTOR, now=edge, policy=POLICY)
    late = edge + timedelta(seconds=1)
    err = code(plan_correction, closed, "absent", "present", "r", None, scope=INSTRUCTOR, now=late, policy=POLICY)
    assert (err.code, err.kind) == ("correction_window_passed", "conflict")
    for scope in (DEPARTMENT, ORGANISATION):
        plan_correction(
            closed, "absent", "present", "r", None, scope=scope, now=late + timedelta(days=400), policy=POLICY
        )


def test_correcting_to_the_same_status_or_an_unknown_one_is_invalid():
    err = code(
        plan_correction, closed_session(), "absent", "absent", "r", None, scope=INSTRUCTOR, now=ENDS, policy=POLICY
    )
    assert (err.code, err.kind) == ("status_unchanged", "invalid")
    assert (
        code(
            plan_correction, closed_session(), "absent", "asleep", "r", None, scope=INSTRUCTOR, now=ENDS, policy=POLICY
        ).code
        == "invalid_choice"
    )
    assert (
        code(
            plan_correction, closed_session(), "absent", "present", "r", None, scope="anyone", now=ENDS, policy=POLICY
        ).field
        == "scope"
    )
