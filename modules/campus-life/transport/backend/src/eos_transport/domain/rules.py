"""Domain rules of transport (docs/prd.md, "Main flows" and "Rules"). Pure functions and constants: no framework,
no database. The application layer calls these before it changes state."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

PASS_STATUSES = ("requested", "issued", "rejected", "cancelled", "expired")
TRIP_STATUSES = ("running", "completed")
NOTICE_KINDS = ("delay", "cancellation", "route-change", "general")
NOTICE_STATUSES = ("current", "expired", "withdrawn")
RIDER_TYPES = ("student", "staff")

# A pass in one of these blocks another pass for the same person over the same dates.
PASS_BLOCKING = ("requested", "issued")

# Allowed transitions: action -> (from statuses, to status).
PASS_TRANSITIONS = {
    "issue": (("requested",), "issued"),
    "reject": (("requested",), "rejected"),
    "cancel": (("requested", "issued"), "cancelled"),
    "expire": (("issued",), "expired"),
}

# Vehicle documents that block assigning the vehicle to a route once expired (PRD rule). The permit is tracked
# and flagged before expiry but does not block assignment.
BLOCKING_VEHICLE_DOCUMENTS = ("insurance", "fitness")
VEHICLE_DOCUMENTS = ("insurance", "fitness", "permit")
DRIVER_DOCUMENTS = ("licence",)


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


# ---------------------------------------------------------------- routes


def check_route_stops(stops: list[dict]) -> list[dict]:
    """Stops of a route, ordered by sequence. At least two, each stop once, each sequence once."""
    if len(stops) < 2:
        raise RuleViolationError("invalid_stops", "a route needs at least two stops")
    ids = [s["stop_id"] for s in stops]
    if len(set(ids)) != len(ids):
        raise RuleViolationError("invalid_stops", "a stop appears more than once on the route")
    seqs = [s["sequence"] for s in stops]
    if len(set(seqs)) != len(seqs):
        raise RuleViolationError("invalid_stops", "two stops have the same sequence")
    return sorted(stops, key=lambda s: s["sequence"])


# ---------------------------------------------------------------- compliance


def is_expired(expires_on: date | None, today: date) -> bool:
    """A document is expired from the day after its expiry date. No date recorded is not expired."""
    return expires_on is not None and expires_on < today


def expires_within(expires_on: date | None, today: date, days: int) -> bool:
    """Expired already, or expiring within `days` from today."""
    return expires_on is not None and expires_on <= today + timedelta(days=days)


def check_assignable(
    vehicle_active: bool, vehicle_documents: dict[str, date | None], driver_active: bool, licence: date, today: date
) -> None:
    """A route may only get an active vehicle with valid insurance and fitness and an active, licensed driver."""
    if not vehicle_active:
        raise RuleViolationError("vehicle_inactive", "the vehicle is inactive")
    if not driver_active:
        raise RuleViolationError("driver_inactive", "the driver is inactive")
    for doc in BLOCKING_VEHICLE_DOCUMENTS:
        if is_expired(vehicle_documents.get(doc), today):
            raise RuleViolationError("document_expired", f"the vehicle's {doc} expired on {vehicle_documents[doc]}")
    if is_expired(licence, today):
        raise RuleViolationError("document_expired", f"the driver's licence expired on {licence}")


# ---------------------------------------------------------------- passes


def check_pass_period(start: date, end: date, today: date) -> None:
    if end < start:
        raise RuleViolationError("invalid_dates", "valid_to must not be before valid_from")
    if end < today:
        raise RuleViolationError("invalid_dates", "valid_to is in the past")


def periods_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def check_capacity(capacity: int | None, issued: int, override: bool, reason: str | None) -> None:
    """Issued passes on a route never exceed its vehicle's capacity unless the office overrides with a reason.
    A route without a vehicle has no seats, so issuing on it is an override too."""
    if capacity is not None and issued < capacity:
        return
    if not override:
        what = "the route has no vehicle assigned" if capacity is None else f"all {capacity} seats are taken"
        raise RuleViolationError("route_full", f"{what}; issue with override_capacity and a reason")
    if not (reason or "").strip():
        raise RuleViolationError("reason_required", "a reason is required to override the capacity")


def pass_covers(status: str, valid_from: date, valid_to: date, on: date) -> bool:
    """An issued pass that is valid on `on`."""
    return status == "issued" and valid_from <= on <= valid_to


# ---------------------------------------------------------------- trips and positions


def check_delay(delay_minutes: int) -> None:
    if delay_minutes < 0:
        raise RuleViolationError("invalid_delay", "delay_minutes must not be negative")


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_stop(
    position: tuple[float, float] | None, stops: list[tuple[str, float | None, float | None]]
) -> str | None:
    """The stop closest to the vehicle's last position: what the rider sees as the stop it is at or nearing.
    Stops without coordinates are skipped; None without a position or without any located stop."""
    if position is None:
        return None
    located = [(sid, lat, lon) for sid, lat, lon in stops if lat is not None and lon is not None]
    if not located:
        return None
    return min(located, key=lambda s: distance_km(position[0], position[1], s[1], s[2]))[0]


# ---------------------------------------------------------------- notices


def notice_status(withdrawn_at: datetime | None, expires_at: datetime | None, now: datetime) -> str:
    if withdrawn_at is not None:
        return "withdrawn"
    if expires_at is not None and expires_at <= now:
        return "expired"
    return "current"


def notice_visible_to(notice_route_id: str | None, rider_route_ids: set[str]) -> bool:
    """A rider sees notices to all routes plus notices to the routes of their current passes."""
    return notice_route_id is None or notice_route_id in rider_route_ids
