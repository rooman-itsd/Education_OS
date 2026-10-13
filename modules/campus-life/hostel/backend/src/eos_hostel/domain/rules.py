"""Domain rules of hostel (docs/prd.md, "Main flows" and "Rules"). Pure functions and constants: no framework,
no database. The application layer calls these before it changes state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

ROOM_STATUSES = ("open", "closed")
ALLOCATION_STATUSES = ("requested", "confirmed", "occupied", "vacated", "cancelled")
# A leave request is the gate pass: out means security recorded the resident leaving.
LEAVE_STATUSES = ("requested", "approved", "rejected", "withdrawn", "out", "returned")
INCIDENT_STATUSES = ("open", "closed")
NOTICE_STATUSES = ("current", "expired", "withdrawn")

# An allocation in one of these holds its bed.
BED_HOLDING = ("confirmed", "occupied")
# A person may have only one of these per academic year (one open request or allocation).
OPEN_FOR_YEAR = ("requested", "confirmed", "occupied")
# Leave in these blocks another leave over the same dates.
LEAVE_BLOCKING = ("requested", "approved", "out")
# Leave in these is overdue once its end has passed: the resident is not back.
LEAVE_AWAY = ("approved", "out")

# Allowed transitions: action -> (from statuses, to status).
ALLOCATION_TRANSITIONS = {
    "confirm": (("requested",), "confirmed"),
    "check_in": (("confirmed",), "occupied"),
    "check_out": (("occupied",), "vacated"),
    "cancel": (("requested", "confirmed"), "cancelled"),
}
LEAVE_TRANSITIONS = {
    "approve": (("requested",), "approved"),
    "reject": (("requested",), "rejected"),
    "withdraw": (("requested",), "withdrawn"),
    # Security at the gate.
    "gate_out": (("approved",), "out"),
    "gate_in": (("out",), "returned"),
    # The warden, when the gate did not record it (for example a hostel without a security desk).
    "return": (("approved", "out"), "returned"),
}

ID_NOTE_MAX_DIGITS = 4


class RuleViolationError(Exception):
    """A domain rule refused the change. `code` is stable; the API maps it to a status."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def transition(transitions: dict, action: str, current: str) -> str:
    """The status after `action`, or RuleViolationError when `current` does not allow it."""
    allowed_from, to = transitions[action]
    if current not in allowed_from:
        raise RuleViolationError("invalid_status", f"cannot {action.replace('_', ' ')} when status is {current}")
    return to


# ---------------------------------------------------------------- rooms and beds


def bed_labels(capacity: int) -> list[str]:
    """Beds of a room are numbered 1..capacity."""
    return [str(n) for n in range(1, capacity + 1)]


def check_bed(capacity: int, bed: str) -> None:
    if bed not in bed_labels(capacity):
        raise RuleViolationError("invalid_bed", f"bed {bed} does not exist; beds are 1 to {capacity}")


def check_capacity_change(new_capacity: int, held_beds: list[str]) -> None:
    """Capacity cannot drop below current occupancy, nor below a bed number that is held."""
    if new_capacity < len(held_beds):
        raise RuleViolationError("capacity_below_occupancy", f"{len(held_beds)} beds are held; capacity {new_capacity}")
    beyond = [b for b in held_beds if b.isdigit() and int(b) > new_capacity]
    if beyond:
        raise RuleViolationError("capacity_below_occupancy", f"bed {beyond[0]} is held and would no longer exist")


@dataclass(frozen=True)
class Period:
    """Dates of an allocation. `end` None means open-ended."""

    start: date
    end: date | None = None

    def overlaps(self, other: Period) -> bool:
        a_end = self.end or date.max
        b_end = other.end or date.max
        return self.start <= b_end and other.start <= a_end


def check_period(start: date, end: date | None) -> Period:
    if end is not None and end < start:
        raise RuleViolationError("invalid_dates", "to must not be before from")
    return Period(start, end)


def free_beds(capacity: int, held_beds: list[str]) -> list[str]:
    held = set(held_beds)
    return [b for b in bed_labels(capacity) if b not in held]


# ---------------------------------------------------------------- leave


def check_leave_window(start: datetime, end: datetime) -> None:
    if end <= start:
        raise RuleViolationError("invalid_dates", "to must be after from")


def windows_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def is_overdue(status: str, end: datetime, now: datetime) -> bool:
    """Approved or out leave whose end has passed without a return."""
    return status in LEAVE_AWAY and end < now


def check_not_own_decision(requester_id: str, decider_id: str) -> None:
    if requester_id == decider_id:
        raise RuleViolationError("own_request", "nobody can decide their own leave request")


# ---------------------------------------------------------------- visitors and notices


def check_id_document_note(note: str | None) -> None:
    """Type and last digits only; never the full document number."""
    if note and len(re.findall(r"\d", note)) > ID_NOTE_MAX_DIGITS:
        raise RuleViolationError(
            "id_number_too_long", f"record the document type and at most the last {ID_NOTE_MAX_DIGITS} digits"
        )


def notice_status(withdrawn_at: datetime | None, expires_at: datetime | None, now: datetime) -> str:
    if withdrawn_at is not None:
        return "withdrawn"
    if expires_at is not None and expires_at <= now:
        return "expired"
    return "current"


def notice_visible_to(notice_hostel_id: str | None, resident_hostel_id: str | None) -> bool:
    """A resident sees their hostel's notices plus notices to every hostel; without a hostel, only the latter."""
    return notice_hostel_id is None or (resident_hostel_id is not None and notice_hostel_id == resident_hostel_id)
