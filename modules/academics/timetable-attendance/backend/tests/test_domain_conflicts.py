"""Unit tests of conflict detection (domain layer): FR-4."""

import uuid
from datetime import date, time

from eos_timetable_attendance.domain.conflicts import blocking, find_conflicts, location_key
from eos_timetable_attendance.domain.timetables import Slot


def uid() -> str:
    return str(uuid.uuid4())


def slot(**over) -> Slot:
    base = {
        "id": uid(),
        "day_of_week": "monday",
        "start_time": time(9),
        "end_time": time(10),
        "course_offering_id": uid(),
        "section_id": uid(),
        "instructor_assignment_id": uid(),
    }
    return Slot(**{**base, **over})


def test_no_conflict_without_a_shared_resource():
    assert find_conflicts([slot(), slot()], {}) == []


def test_same_section_overlapping_is_a_blocking_conflict():
    section = uid()
    a, b = slot(section_id=section), slot(section_id=section, start_time=time(9, 30), end_time=time(10, 30))
    [c] = find_conflicts([a, b], {})
    assert (c.kind, c.blocking, c.shared_id, c.overlap_start, c.overlap_end) == (
        "section",
        True,
        section,
        time(9, 30),
        time(10, 0),
    )
    assert c.other_timetable_id is None
    assert c.slot_id < c.other_slot_id  # a pair inside one timetable is reported once, lower id first


def test_same_instructor_through_different_assignments_is_blocking():
    a, b = slot(), slot()
    teacher = uid()
    [c] = find_conflicts([a, b], {a.instructor_assignment_id: teacher, b.instructor_assignment_id: teacher})
    assert (c.kind, c.blocking, c.shared_id) == ("instructor", True, teacher)


def test_an_assignment_missing_from_the_read_model_never_clashes_on_instructor():
    a, b = slot(), slot()
    assert find_conflicts([a, b], {a.instructor_assignment_id: uid()}) == []


def test_location_clash_is_only_a_warning_and_ignores_case_and_spacing():
    a, b = slot(location_label="Room 4"), slot(location_label="room 4")
    [c] = find_conflicts([a, b], {})
    assert (c.kind, c.blocking, c.shared_id) == ("location", False, "room 4")
    assert blocking([c]) == []
    assert find_conflicts([slot(location_label=None), slot(location_label=None)], {}) == []


def test_back_to_back_other_day_and_disjoint_dates_do_not_conflict():
    section = uid()
    a = slot(section_id=section)
    assert find_conflicts([a, slot(section_id=section, start_time=time(10), end_time=time(11))], {}) == []
    assert find_conflicts([a, slot(section_id=section, day_of_week="tuesday")], {}) == []
    early = slot(section_id=section, effective_to=date(2026, 8, 31))
    late = slot(section_id=section, effective_from=date(2026, 9, 1))
    assert find_conflicts([early, late], {}) == []


def test_one_pair_can_clash_on_several_kinds():
    section, teacher = uid(), uid()
    a, b = slot(section_id=section), slot(section_id=section)
    found = find_conflicts([a, b], {a.instructor_assignment_id: teacher, b.instructor_assignment_id: teacher})
    assert [c.kind for c in found] == ["section", "instructor"]


def test_conflicts_with_other_published_timetables_name_that_timetable():
    section = uid()
    mine, theirs = slot(section_id=section), slot(section_id=section)
    other_timetable = uid()
    [c] = find_conflicts([mine], {}, others=[(other_timetable, theirs)])
    assert (c.slot_id, c.other_slot_id, c.other_timetable_id) == (mine.id, theirs.id, other_timetable)


def test_a_slot_is_not_compared_with_itself_in_another_timetable():
    s = slot()
    assert find_conflicts([s], {}, others=[(uid(), s)]) == []


def test_the_result_is_ordered_by_day_then_time_and_repeatable():
    section = uid()
    slots = [slot(section_id=section, day_of_week="wednesday"), slot(section_id=section, day_of_week="wednesday")]
    slots += [slot(section_id=section, start_time=time(9, 30), end_time=time(10, 30)) for _ in range(2)]
    slots += [slot(section_id=section, start_time=time(9, 15), end_time=time(9, 45))]
    first = find_conflicts(slots, {})
    assert first == find_conflicts(list(reversed(slots)), {})
    keys = [(c.day_of_week, c.overlap_start) for c in first]
    assert keys == sorted(keys)


def test_location_key():
    assert location_key(None) is None
    assert location_key("  ") is None
    assert location_key(" A  B ") == "a b"
