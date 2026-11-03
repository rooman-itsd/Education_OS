"""Unit tests of the timetable rules (domain layer): FR-1 to FR-3."""

import uuid
from datetime import UTC, date, time

import pytest
from eos_timetable_attendance.domain.errors import DomainRuleError
from eos_timetable_attendance.domain.timetables import (
    DRAFT,
    PUBLISHED,
    UNPUBLISHED,
    Slot,
    Timetable,
    ensure_editable,
    ensure_known_references,
    ensure_offerings_in_period,
    ensure_unique_slots,
    new_slot,
    plan_publish,
    plan_unpublish,
)


def uid() -> str:
    return str(uuid.uuid4())


def slot(**over) -> Slot:
    base = {
        "id": uid(),
        "day_of_week": "monday",
        "start_time": time(9, 0),
        "end_time": time(10, 0),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
    }
    return Slot(**{**base, **over})


def timetable(**over) -> Timetable:
    return Timetable(**{"id": uid(), "academic_period_id": uid(), "name": "Odd term", **over})


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


def test_slot_end_must_be_after_start():
    assert code(slot, end_time=time(9, 0)).code == "invalid_slot_times"
    assert code(slot, start_time=time(11, 0)).field == "end_time"


@pytest.mark.parametrize("field", ["course_offering_id", "section_id", "instructor_assignment_id", "id"])
def test_slot_ids_must_be_uuids(field):
    err = code(slot, **{field: "not-a-uuid"})
    assert (err.code, err.kind, err.field) == ("invalid_id", "invalid", field)


def test_slot_day_must_be_a_contract_day():
    assert code(slot, day_of_week="funday").code == "invalid_choice"


def test_slot_times_cannot_carry_a_zone():
    assert code(slot, start_time=time(9, 0, tzinfo=UTC)).code == "invalid_time"


def test_slot_effective_dates_must_be_ordered():
    assert code(slot, effective_from=date(2026, 8, 2), effective_to=date(2026, 8, 1)).code == "invalid_effective_dates"
    assert slot(effective_from=date(2026, 8, 1), effective_to=date(2026, 8, 1)).effective_to == date(2026, 8, 1)


def test_new_slot_trims_the_location_and_blank_means_none():
    data = {
        "day_of_week": "tuesday",
        "start_time": time(9),
        "end_time": time(10),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
    }
    assert new_slot(uid(), {**data, "location_label": "  Room 4 "}).location_label == "Room 4"
    assert new_slot(uid(), {**data, "location_label": "   "}).location_label is None
    assert new_slot(uid(), data).location_label is None


def test_slot_dates_overlap_with_open_bounds():
    a = slot(effective_from=date(2026, 8, 1), effective_to=date(2026, 8, 31))
    assert a.dates_overlap(slot())
    assert a.dates_overlap(slot(effective_from=date(2026, 8, 31)))
    assert not a.dates_overlap(slot(effective_from=date(2026, 9, 1)))
    assert not a.dates_overlap(slot(effective_to=date(2026, 7, 31)))


def test_slot_times_overlap_only_on_the_same_day_and_not_back_to_back():
    a = slot()
    assert a.times_overlap(slot(start_time=time(9, 30), end_time=time(10, 30))) == (time(9, 30), time(10, 0))
    assert a.times_overlap(slot(start_time=time(10, 0), end_time=time(11, 0))) is None
    assert a.times_overlap(slot(day_of_week="tuesday")) is None


def test_timetable_validates_its_fields():
    assert code(timetable, name="  ").code == "invalid_name"
    assert code(timetable, name="x" * 201).code == "invalid_name"
    assert code(timetable, status="live").code == "invalid_choice"
    assert code(timetable, department_id="x").field == "department_id"
    assert code(timetable, academic_period_id="x").field == "academic_period_id"


def test_only_a_draft_or_unpublished_timetable_is_editable():
    ensure_editable(timetable())
    ensure_editable(timetable(status=UNPUBLISHED))
    err = code(ensure_editable, timetable(status=PUBLISHED))
    assert (err.code, err.kind) == ("timetable_published", "conflict")


def test_duplicate_slot_ids_are_refused():
    s = slot()
    ensure_unique_slots([s, slot()])
    assert code(ensure_unique_slots, [s, s]).code == "duplicate_slot"


def references(s: Slot) -> dict:
    return {
        "offerings": {s.course_offering_id},
        "sections": {s.section_id: s.course_offering_id},
        "assignments": {s.instructor_assignment_id: (s.course_offering_id, s.section_id)},
    }


def test_known_references_pass():
    s = slot()
    ensure_known_references([s], **references(s))
    whole = references(s) | {"assignments": {s.instructor_assignment_id: (s.course_offering_id, None)}}
    ensure_known_references([s], **whole)  # an assignment to the whole offering covers any of its sections


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"offerings": set()}, "unknown_course_offering"),
        ({"sections": {}}, "unknown_section"),
        ({"assignments": {}}, "unknown_instructor_assignment"),
    ],
)
def test_unknown_references_are_unprocessable(change, expected):
    s = slot()
    err = code(ensure_known_references, [s], **(references(s) | change))
    assert (err.code, err.kind) == (expected, "unprocessable")


def test_references_must_agree_with_each_other():
    s = slot()
    other = uid()
    wrong_offering = references(s) | {"sections": {s.section_id: other}}
    assert code(ensure_known_references, [s], **wrong_offering).code == "section_not_in_offering"
    wrong_assignment = references(s) | {"assignments": {s.instructor_assignment_id: (other, s.section_id)}}
    assert code(ensure_known_references, [s], **wrong_assignment).code == "assignment_mismatch"
    wrong_section = references(s) | {"assignments": {s.instructor_assignment_id: (s.course_offering_id, other)}}
    assert code(ensure_known_references, [s], **wrong_section).code == "assignment_mismatch"


def test_publishing_raises_the_version_each_time():
    first = plan_publish(timetable(), blocking_conflicts=0).timetable
    assert (first.status, first.version) == (PUBLISHED, 1)
    again = plan_publish(plan_unpublish(first).timetable, blocking_conflicts=0).timetable
    assert (again.status, again.version) == (PUBLISHED, 2)


def test_publishing_refuses_blocking_conflicts_and_a_published_timetable():
    err = code(plan_publish, timetable(), blocking_conflicts=2)
    assert (err.code, err.kind, err.details) == ("blocking_conflicts", "conflict", {"blocking_conflicts": 2})
    assert code(plan_publish, timetable(status=PUBLISHED), blocking_conflicts=0).code == "already_published"


def test_unpublishing_needs_a_published_timetable_and_keeps_the_version():
    done = plan_unpublish(timetable(status=PUBLISHED, version=3)).timetable
    assert (done.status, done.version) == (UNPUBLISHED, 3)
    assert code(plan_unpublish, timetable(status=DRAFT)).code == "not_published"
    assert code(plan_unpublish, timetable(status=UNPUBLISHED, version=1)).kind == "conflict"


def test_every_offering_must_belong_to_the_timetables_period():
    s, period, other = slot(), uid(), uid()
    ensure_offerings_in_period([s], {s.course_offering_id: period}, period)
    ensure_offerings_in_period([s], {}, period)  # an unknown offering is ensure_known_references' business
    err = code(ensure_offerings_in_period, [s], {s.course_offering_id: other}, period)
    assert (err.code, err.kind, err.field) == ("offering_not_in_period", "unprocessable", "course_offering_id")
