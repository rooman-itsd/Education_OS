"""Timetable conflict detection (contract `TimetableConflict`; PRD FR-4).

Two slots conflict when their times overlap on the same weekday, their effective dates overlap, and they share
a section or an instructor (blocking), or a location label (a warning only, until room ownership is settled: Q4).
Back-to-back slots do not overlap."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import time

from .timetables import Slot

SECTION, INSTRUCTOR, LOCATION = "section", "instructor", "location"
CONFLICT_KINDS = (SECTION, INSTRUCTOR, LOCATION)  # contract ConflictKind
BLOCKING_KINDS = (SECTION, INSTRUCTOR)


@dataclass(frozen=True)
class Conflict:
    kind: str
    blocking: bool
    slot_id: str
    other_slot_id: str
    other_timetable_id: str | None
    day_of_week: str
    overlap_start: time
    overlap_end: time
    shared_id: str  # the section id, the instructor id or the location label the two slots share


def location_key(label: str | None) -> str | None:
    """Labels are free text (Q4), so two spellings of one room differing only in case or spacing are the same."""
    if label is None:
        return None
    key = " ".join(label.split()).casefold()
    return key or None


def _shared(slot: Slot, other: Slot, instructors: Mapping[str, str]) -> list[tuple[str, str]]:
    shared: list[tuple[str, str]] = []
    if slot.section_id == other.section_id:
        shared.append((SECTION, slot.section_id))
    mine, theirs = instructors.get(slot.instructor_assignment_id), instructors.get(other.instructor_assignment_id)
    if mine is not None and mine == theirs:
        shared.append((INSTRUCTOR, mine))
    place = location_key(slot.location_label)
    if place is not None and place == location_key(other.location_label):
        shared.append((LOCATION, place))
    return shared


def find_conflicts(
    slots: Iterable[Slot],
    instructors: Mapping[str, str],
    others: Iterable[tuple[str, Slot]] = (),
) -> list[Conflict]:
    """The conflicts among `slots` and between `slots` and `others`.

    `instructors` maps an instructor assignment id to the instructor it stands for (from the local read model); an
    assignment missing from it can never clash on the instructor. `others` are (timetable id, slot) pairs of every
    other published timetable of the same academic period (FR-4); each is compared with every slot given.

    A pair inside `slots` is reported once, with the lower slot id first. A pair with an other timetable is reported
    with the given slot as `slot_id`. The result is ordered by weekday, start of the overlap, kind, then slot ids, so
    it is the same on every call."""
    mine = list(slots)
    found: list[Conflict] = []
    for i, slot in enumerate(mine):
        for other in mine[i + 1 :]:
            first, second = sorted((slot, other), key=lambda s: s.id)
            found.extend(_between(first, second, None, instructors))
        for timetable_id, other in others:
            if other.id != slot.id:
                found.extend(_between(slot, other, timetable_id, instructors))
    order = {k: n for n, k in enumerate(CONFLICT_KINDS)}
    return sorted(
        found,
        key=lambda c: (
            c.day_of_week,
            c.overlap_start,
            order[c.kind],
            c.slot_id,
            c.other_slot_id,
            c.other_timetable_id or "",
        ),
    )


def _between(slot: Slot, other: Slot, other_timetable_id: str | None, instructors: Mapping[str, str]) -> list[Conflict]:
    window = slot.times_overlap(other)
    if window is None or not slot.dates_overlap(other):
        return []
    return [
        Conflict(
            kind=kind,
            blocking=kind in BLOCKING_KINDS,
            slot_id=slot.id,
            other_slot_id=other.id,
            other_timetable_id=other_timetable_id,
            day_of_week=slot.day_of_week,
            overlap_start=window[0],
            overlap_end=window[1],
            shared_id=shared_id,
        )
        for kind, shared_id in _shared(slot, other, instructors)
    ]


def blocking(conflicts: Iterable[Conflict]) -> list[Conflict]:
    return [c for c in conflicts if c.blocking]
