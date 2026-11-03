"""Attendance reports (contracts `OfferingAttendance`, `StudentEligibilityAttendance`; PRD FR-13, FR-14, FR-18).

Percentages are computed from records, never entered. `excused` classes leave the denominator (owner decision C7);
`attended` is present plus late."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .attendance import ABSENT, ATTENDANCE_STATUSES, ATTENDED, EXCUSED, LATE, PRESENT

HUNDRED = Decimal(100)
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Tally:
    """Attendance of one student (or one group) over the classes counted."""

    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0

    @property
    def attended(self) -> int:
        return self.present + self.late

    @property
    def held(self) -> int:
        """Classes counted: every class except those the student was excused from (the denominator)."""
        return self.present + self.late + self.absent

    @property
    def percentage(self) -> Decimal | None:
        """Attended over held, as a percentage to two places (halves round up); None when nothing was held."""
        if self.held == 0:
            return None
        return (Decimal(self.attended) * HUNDRED / Decimal(self.held)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def below(self, threshold_percent: int) -> bool:
        """Whether attendance is under the shortage threshold. Exact integer arithmetic, on the unrounded value, so
        74.996 is short of 75 even though it prints as 75.00. A tally with no class held is not short."""
        return self.held > 0 and self.attended * 100 < threshold_percent * self.held

    def plus(self, other: Tally) -> Tally:
        return Tally(
            self.present + other.present,
            self.late + other.late,
            self.absent + other.absent,
            self.excused + other.excused,
        )


def tally(statuses: Iterable[str]) -> Tally:
    """The tally of recorded statuses (of closed sessions; the caller leaves open ones out)."""
    counted = Counter(statuses)
    unknown = set(counted) - set(ATTENDANCE_STATUSES)
    if unknown:
        raise ValueError(f"unknown attendance status {sorted(unknown)}")
    return Tally(counted[PRESENT], counted[LATE], counted[ABSENT], counted[EXCUSED])


def no_eligible_classes(t: Tally) -> bool:
    """FR-18: a student with no counted class is flagged, not given a percentage."""
    return t.held == 0


__all__ = ["ATTENDED", "Tally", "no_eligible_classes", "tally"]
