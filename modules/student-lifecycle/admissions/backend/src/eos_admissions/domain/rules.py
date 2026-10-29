"""Admissions business rules. Pure functions: each returns a value or raises RuleViolationError with a code
from the contract's ConflictError or RuleError list. Mapping codes to HTTP statuses is the application's job."""

from __future__ import annotations

import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from .enums import (
    ACCEPTED,
    APPLICATION_STATUSES,
    DECLINED,
    DOCUMENTS_OPEN,
    ELIGIBLE,
    OFFER_EXPIRED,
    OFFER_OPEN,
    OFFERED,
    PUBLISHED,
    STAFF_TRANSITIONS,
    TERMINAL,
)


class RuleViolationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_status_change(current: str, target: str, reason: str | None) -> None:
    if current in TERMINAL:
        raise RuleViolationError("terminal_status", f"Application is {current} and cannot change status")
    if target not in STAFF_TRANSITIONS.get(current, frozenset()):
        raise RuleViolationError("invalid_transition", f"Cannot move an application from {current} to {target}")
    if not reason or not reason.strip():
        raise RuleViolationError("reason_required", "A reason is required for a status change")


def check_can_offer(status: str, has_open_offer: bool) -> None:
    if has_open_offer:
        raise RuleViolationError("offer_already_exists", "Application already has an open offer")
    if status != ELIGIBLE:
        raise RuleViolationError("not_eligible", f"Only an eligible application can receive an offer; it is {status}")


def check_documents_open(status: str) -> None:
    if status not in DOCUMENTS_OPEN:
        raise RuleViolationError("documents_closed", f"Application is {status} and no longer accepts documents")


def effective_offer_status(status: str, expires_at: datetime | None, now: datetime) -> str:
    """An open offer whose expires_at has passed is expired, whether or not anyone has written that down yet."""
    if status == OFFER_OPEN and expires_at is not None and expires_at <= now:
        return OFFER_EXPIRED
    return status


def check_offer_decidable(effective_status: str) -> None:
    if effective_status != OFFER_OPEN:
        raise RuleViolationError("no_open_offer", f"No open offer on this application (offer is {effective_status})")


def check_can_publish(status: str) -> None:
    if status == PUBLISHED:
        raise RuleViolationError("merit_list_already_published", "Merit list is already published")


def validate_scores(scores: Iterable[tuple[str, float]], eligible_ids: set[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for application_id, score in scores:
        if application_id in result:
            raise RuleViolationError("duplicate_score", f"Application {application_id} is scored more than once")
        if application_id not in eligible_ids:
            raise RuleViolationError(
                "score_for_ineligible_application",
                f"Application {application_id} is not eligible for this programme and academic year",
            )
        result[application_id] = score
    return result


@dataclass(frozen=True)
class RankedEntry:
    application_id: str
    rank: int
    score: float | None


def rank_entries(candidates: Iterable[tuple[str, datetime]], scores: Mapping[str, float]) -> list[RankedEntry]:
    """Highest score first, ties by earliest submission; unscored after every scored one, in submission order.
    The application id breaks any remaining tie so the order never depends on input order."""

    def key(candidate: tuple[str, datetime]) -> tuple:
        application_id, submitted_at = candidate
        if application_id in scores:
            return (0, -scores[application_id], submitted_at, application_id)
        return (1, 0.0, submitted_at, application_id)

    ordered = sorted(candidates, key=key)
    return [RankedEntry(app_id, rank, scores.get(app_id)) for rank, (app_id, _) in enumerate(ordered, start=1)]


def funnel(by_status: Mapping[str, int]) -> dict:
    """Stages from current statuses. An application withdrawn after eligibility counts only as applied."""
    counts = {status: int(by_status.get(status, 0)) for status in APPLICATION_STATUSES}
    offered = counts[OFFERED] + counts[ACCEPTED] + counts[DECLINED]
    return {
        "total": sum(counts.values()),
        "stages": {
            "applied": sum(counts.values()),
            "eligible": counts[ELIGIBLE] + offered,
            "offered": offered,
            "accepted": counts[ACCEPTED],
        },
        "by_status": counts,
    }


def generate_reference_number(prefix: str = "ADM", when: datetime | None = None) -> str:
    """ADM-2026-A1B2C3. Unique per organisation is enforced by the database; callers retry on a collision."""
    year = (when or datetime.now(UTC)).year
    return f"{prefix}-{year}-{secrets.token_hex(3).upper()}"


def normalise_email(email: str) -> str:
    return email.strip().lower()
