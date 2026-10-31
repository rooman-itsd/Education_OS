"""Domain rules of tournament-events (docs/prd.md). Pure functions over plain values: no framework, no database.

Tournament lifecycle. The stored status is `draft`, `published` or `cancelled`; `ongoing` and `completed` are read
from the dates of a published tournament against the institution's local date (`effective_status`):

    draft --publish--> published --(start_date reached)--> ongoing --(end_date passed)--> completed
    draft | published | ongoing --cancel--> cancelled

Fixture lifecycle (`check_fixture_transition`); `completed` is reached only by recording a result:

    scheduled -> in_progress | postponed | cancelled
    postponed -> scheduled | cancelled
    in_progress -> postponed | cancelled
    scheduled | in_progress | completed --record result--> completed

Entry lifecycle (`check_entry_transition`): pending -> confirmed | withdrawn, confirmed -> withdrawn; withdrawn is
final."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import date, datetime

DRAFT, PUBLISHED, ONGOING, COMPLETED, CANCELLED = "draft", "published", "ongoing", "completed", "cancelled"
SCHEDULED, IN_PROGRESS, POSTPONED = "scheduled", "in_progress", "postponed"
PENDING, CONFIRMED, WITHDRAWN = "pending", "confirmed", "withdrawn"

FIXTURE_MOVES = {
    SCHEDULED: frozenset({IN_PROGRESS, POSTPONED, CANCELLED}),
    POSTPONED: frozenset({SCHEDULED, CANCELLED}),
    IN_PROGRESS: frozenset({POSTPONED, CANCELLED}),
    COMPLETED: frozenset(),
    CANCELLED: frozenset(),
}
# Fixtures still to be played; cancelling the tournament cancels these.
OPEN_FIXTURES = frozenset({SCHEDULED, POSTPONED, IN_PROGRESS})
# A result may be recorded (or corrected) for a fixture in one of these states.
RESULT_STATES = frozenset({SCHEDULED, IN_PROGRESS, COMPLETED})
ENTRY_MOVES = {
    PENDING: frozenset({CONFIRMED, WITHDRAWN}),
    CONFIRMED: frozenset({WITHDRAWN}),
    WITHDRAWN: frozenset(),
}


class RuleViolationError(Exception):
    """A request the rules refuse. The API answers 400 with {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- tournaments


def effective_status(stored: str, start: date, end: date, today: date) -> str:
    """What a tournament is now. Only a published tournament moves on by itself, as its dates arrive."""
    if stored != PUBLISHED:
        return stored
    if today > end:
        return COMPLETED
    if today >= start:
        return ONGOING
    return PUBLISHED


def check_tournament_dates(start: date, end: date, registration_closes_on: date | None) -> None:
    if end < start:
        raise RuleViolationError("end_before_start", "end_date cannot be before start_date")
    if registration_closes_on is not None and registration_closes_on > end:
        raise RuleViolationError("registration_after_end", "registration_closes_on cannot be after end_date")


def check_editable(status: str) -> None:
    """A tournament can be edited until it is cancelled or completed."""
    if status in (CANCELLED, COMPLETED):
        raise RuleViolationError("tournament_closed", f"a {status} tournament cannot be changed")


def check_publish(status: str) -> None:
    if status != DRAFT:
        raise RuleViolationError("not_draft", f"only a draft can be published; this tournament is {status}")


def check_cancel(status: str) -> None:
    if status == CANCELLED:
        raise RuleViolationError("already_cancelled", "the tournament is already cancelled")
    if status == COMPLETED:
        raise RuleViolationError("tournament_completed", "a completed tournament cannot be cancelled")


def check_running(status: str) -> None:
    """Fixtures, officials, results and logistics change only on a tournament that is not cancelled. Fixtures need
    entries, so they also need the tournament published (checked by check_schedulable)."""
    if status == CANCELLED:
        raise RuleViolationError("tournament_closed", "the tournament is cancelled")


def check_schedulable(status: str) -> None:
    check_running(status)
    if status == DRAFT:
        raise RuleViolationError("tournament_not_published", "publish the tournament before scheduling fixtures")


def check_entries_open(status: str, registration_closes_on: date | None, today: date) -> None:
    """Publishing opens entries; they close on registration_closes_on (inclusive) and when the tournament ends."""
    if status not in (PUBLISHED, ONGOING):
        raise RuleViolationError("entries_not_open", f"entries are not open for a {status} tournament")
    if registration_closes_on is not None and today > registration_closes_on:
        raise RuleViolationError("registration_closed", f"registration closed on {registration_closes_on}")


# ---------------------------------------------------------------- entries


def check_athletes(athlete_ids: Sequence[str]) -> None:
    if not athlete_ids:
        raise RuleViolationError("no_athletes", "an entry needs at least one athlete")
    if len(set(athlete_ids)) != len(athlete_ids):
        raise RuleViolationError("duplicate_athlete", "an athlete appears more than once in the entry")


def check_new_entry_status(status: str) -> None:
    if status == WITHDRAWN:
        raise RuleViolationError("invalid_status", "a new entry is pending or confirmed")


def check_entry_transition(current: str, new: str) -> None:
    if new != current and new not in ENTRY_MOVES[current]:
        raise RuleViolationError("invalid_transition", f"an entry cannot go from {current} to {new}")


def already_entered(athlete_ids: Iterable[str], others: Iterable[Sequence[str]]) -> str | None:
    """The first athlete who already has a live entry in the same category, if any."""
    taken = {a for ids in others for a in ids}
    return next((a for a in athlete_ids if a in taken), None)


# ---------------------------------------------------------------- fixtures


def check_new_fixture_status(status: str) -> None:
    if status != SCHEDULED:
        raise RuleViolationError("invalid_status", "a new fixture is scheduled; record a result to complete it")


def check_fixture_transition(current: str, new: str) -> None:
    if new == current:
        return
    if new == COMPLETED:
        raise RuleViolationError("record_result", "a fixture is completed by recording its result")
    if new not in FIXTURE_MOVES[current]:
        raise RuleViolationError("invalid_transition", f"a fixture cannot go from {current} to {new}")


def check_fixture_editable(status: str) -> None:
    if status in (COMPLETED, CANCELLED):
        raise RuleViolationError("fixture_closed", f"a {status} fixture cannot be changed")


def check_fixture_entries(entry_ids: Sequence[str]) -> None:
    if len(set(entry_ids)) != len(entry_ids):
        raise RuleViolationError("duplicate_entry", "an entry appears more than once in the fixture")


def check_within_dates(local_day: date, start: date, end: date) -> None:
    """A fixture falls on one of the tournament's days (in the institution's local date)."""
    if not start <= local_day <= end:
        raise RuleViolationError("outside_tournament_dates", f"the fixture must be between {start} and {end}")


# ---------------------------------------------------------------- results


def check_result_allowed(fixture_status: str, scheduled_at: datetime, now: datetime) -> None:
    """A result belongs to a fixture that has started (scheduled_at reached) and is not postponed or cancelled.
    Recording again on a completed fixture corrects its result. Both datetimes are timezone-aware."""
    if fixture_status not in RESULT_STATES:
        raise RuleViolationError("fixture_not_playable", f"no result can be recorded for a {fixture_status} fixture")
    if scheduled_at > now:
        raise RuleViolationError("fixture_not_started", "the fixture has not started yet")


def check_placings(placings: Sequence[dict], fixture_entry_ids: Sequence[str]) -> None:
    if not placings:
        raise RuleViolationError("no_placings", "a result needs at least one placing")
    seen: set[str] = set()
    for p in placings:
        if p["entry_id"] not in fixture_entry_ids:
            raise RuleViolationError("entry_not_in_fixture", f"entry {p['entry_id']} is not in this fixture")
        if p["entry_id"] in seen:
            raise RuleViolationError("duplicate_placing", f"entry {p['entry_id']} is placed more than once")
        seen.add(p["entry_id"])
        if p.get("position") is not None and p["position"] < 1:
            raise RuleViolationError("invalid_position", "a position is 1 or more")
        if p.get("mark") is not None and not math.isfinite(p["mark"]):
            raise RuleViolationError("invalid_mark", "a mark is a finite number")


# ---------------------------------------------------------------- logistics


def check_travel(departure_at: datetime | None, return_at: datetime | None, travelling_count: int | None) -> None:
    if departure_at is not None and return_at is not None and return_at < departure_at:
        raise RuleViolationError("return_before_departure", "return_at cannot be before departure_at")
    if travelling_count is not None and travelling_count < 0:
        raise RuleViolationError("invalid_count", "travelling_count cannot be negative")
