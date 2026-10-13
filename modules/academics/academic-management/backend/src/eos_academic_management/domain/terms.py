"""Academic terms (contract `Term`; PRD FR-1, FR-2)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from .errors import DomainRuleError
from .values import require_choice

UPCOMING, ACTIVE, CLOSED = "upcoming", "active", "closed"
TERM_STATUSES = (UPCOMING, ACTIVE, CLOSED)  # contract TermStatus


def _require_date(value: object, field: str) -> date:
    """A calendar date (contract `format: date`). datetime is a subclass of date but carries a time, so it is
    rejected rather than compared."""
    if isinstance(value, datetime) or not isinstance(value, date):
        raise DomainRuleError("invalid_date", f"{field} must be a date without a time", kind="invalid", field=field)
    return value


@dataclass(frozen=True)
class DateRange:
    """An inclusive range of dates: a term runs from starts_on to ends_on, both days included."""

    starts_on: date
    ends_on: date

    def __post_init__(self) -> None:
        _require_date(self.starts_on, "starts_on")
        _require_date(self.ends_on, "ends_on")
        if self.ends_on < self.starts_on:
            raise DomainRuleError(
                "invalid_term_dates", "ends_on must not be before starts_on", kind="invalid", field="ends_on"
            )

    def overlaps(self, other: DateRange) -> bool:
        return self.starts_on <= other.ends_on and other.starts_on <= self.ends_on

    def contains(self, day: date) -> bool:
        return self.starts_on <= day <= self.ends_on


@dataclass(frozen=True)
class Term:
    id: str
    code: str
    name: str
    dates: DateRange
    status: str = UPCOMING

    def __post_init__(self) -> None:
        require_choice(self.status, "status", TERM_STATUSES)


def ensure_no_overlap(dates: DateRange, existing: Iterable[Term], *, ignore_id: str | None = None) -> None:
    """FR-1: term dates in one organisation do not overlap. `existing` is the organisation's terms; pass
    `ignore_id` when re-checking a term whose dates are being changed.

    `field` names the date that falls inside another term: starts_on if the start does, else ends_on if the
    end does, else None when the new range encloses another term entirely."""
    clashing = sorted((t for t in existing if t.id != ignore_id and t.dates.overlaps(dates)), key=lambda t: t.code)
    if clashing:
        if any(t.dates.contains(dates.starts_on) for t in clashing):
            field: str | None = "starts_on"
        elif any(t.dates.contains(dates.ends_on) for t in clashing):
            field = "ends_on"
        else:
            field = None
        codes = ", ".join(t.code for t in clashing)
        raise DomainRuleError("term_dates_overlap", f"dates overlap term(s) {codes}", kind="conflict", field=field)


@dataclass(frozen=True)
class Activation:
    """What activating a term changes: the term that becomes active and the previously active terms that close."""

    activated_id: str
    closed_ids: tuple[str, ...]


def plan_activation(terms: Iterable[Term], term_id: str) -> Activation:
    """FR-2: exactly one term is active at a time; activating a term closes the previous one.

    Activating the term that is already active changes nothing. Whether a closed term may be activated again is
    not specified by the PRD or the contract, so it is not refused here (open question)."""
    terms = list(terms)
    target = next((t for t in terms if t.id == term_id), None)
    if target is None:
        raise DomainRuleError("term_not_found", f"term {term_id!r} does not exist", kind="not_found")
    closed = tuple(sorted(t.id for t in terms if t.status == ACTIVE and t.id != term_id))
    return Activation(activated_id=term_id, closed_ids=closed)
