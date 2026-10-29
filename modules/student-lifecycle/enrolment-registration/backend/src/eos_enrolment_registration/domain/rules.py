"""Enrolment and registration rules (docs/prd.md §6). Pure functions: each returns a value or raises
RuleViolationError with a code from the contract's ConflictError or RuleError list. HTTP statuses are the
application's job.

Checks on academic-management's data take a snapshot, or None when this module has no local copy yet (no event
received). None skips that check; the registration is then flagged references_verified false (rule 3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from .enums import ACTIVE, CONFIRMED, ENROLMENT_ENDED, OPEN, WINDOW_EXEMPT


class RuleViolationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class OfferingSnapshot:
    course_offering_id: str
    academic_period_id: str
    status: str


@dataclass(frozen=True)
class SectionSnapshot:
    section_id: str
    course_offering_id: str
    capacity: int
    status: str


@dataclass(frozen=True)
class WindowSnapshot:
    opens_at: datetime
    closes_at: datetime


# ---------------------------------------------------------------- enrolment


def check_enrolment_active(status: str) -> None:
    """Rule 1: a registration needs an active programme enrolment."""
    if status != ACTIVE:
        raise RuleViolationError("enrolment_not_active", f"The programme enrolment is {status}, not active")


def check_can_end(status: str) -> None:
    """Rule 8: only an active enrolment can be withdrawn or completed."""
    if status in ENROLMENT_ENDED:
        raise RuleViolationError("enrolment_ended", f"The programme enrolment is already {status}")


def format_roll_number(prefix: str, year: int, number: int) -> str:
    """Rule 7: RN2026-00042. Five digits, widening rather than failing past 99,999."""
    return f"{prefix}{year}-{number:05d}"


# ---------------------------------------------------------------- windows


def validate_window(opens_at: datetime, closes_at: datetime) -> None:
    if closes_at <= opens_at:
        raise RuleViolationError("invalid_window", "closes_at must be after opens_at")


def is_window_open(window: WindowSnapshot | None, now: datetime) -> bool:
    """Open from opens_at (inclusive) until closes_at (exclusive)."""
    return window is not None and window.opens_at <= now < window.closes_at


def check_window(registration_type: str, window: WindowSnapshot | None, now: datetime) -> None:
    """Rule 5: regular registrations need the term's window open; supplementary and backlog do not."""
    if registration_type in WINDOW_EXEMPT:
        return
    if window is None:
        raise RuleViolationError("window_closed", "The term has no registration window")
    if not is_window_open(window, now):
        raise RuleViolationError("window_closed", "The term's registration window is not open")


# ---------------------------------------------------------------- offering and section (the roster's checks)


def check_offering(offering: OfferingSnapshot | None, academic_period_id: str) -> None:
    """Rule 3: when known, the offering is open and belongs to the term given."""
    if offering is None:
        return
    if offering.academic_period_id != academic_period_id:
        raise RuleViolationError("term_mismatch", "The course offering belongs to another term")
    if offering.status != OPEN:
        raise RuleViolationError("offering_not_open", f"The course offering is {offering.status}, not open")


def check_section(section: SectionSnapshot | None, course_offering_id: str, confirmed_count: int) -> None:
    """Rules 3 and 4: when known, the section belongs to the offering, is open, and has a free seat.
    confirmed_count is how many confirmed registrations the section has now, excluding the one being placed."""
    if section is None:
        return
    if section.course_offering_id != course_offering_id:
        raise RuleViolationError("section_not_in_offering", "The section does not belong to the course offering")
    if section.status != OPEN:
        raise RuleViolationError("section_not_open", f"The section is {section.status}, not open")
    if confirmed_count >= section.capacity:
        raise RuleViolationError("section_full", f"The section is full ({section.capacity} seats)")


def references_verified(offering: OfferingSnapshot | None, section: SectionSnapshot | None) -> bool:
    return offering is not None and section is not None


# ---------------------------------------------------------------- registration changes


def check_registration_confirmed(status: str) -> None:
    if status != CONFIRMED:
        raise RuleViolationError("registration_not_confirmed", f"The registration is {status}, not confirmed")


def check_section_change(from_section_id: str, to_section_id: str) -> None:
    if from_section_id == to_section_id:
        raise RuleViolationError("same_section", "The registration is already in that section")


# ---------------------------------------------------------------- report


def rank_offerings(counts: Mapping[str, int], limit: int) -> list[tuple[str, int]]:
    """Busiest offering first; ties by offering id so the order never depends on query order."""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
