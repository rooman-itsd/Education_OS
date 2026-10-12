"""Use cases of facility-booking (docs/prd.md). Each one checks permissions and rules, changes state, and
publishes the matching event from contracts/events.yaml to the outbox in the same transaction. Until the
audit SDK exists, the outbox is the audit trail of every state change (PRD rule 12)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.rules import (
    CHANGEABLE_STATUSES,
    CHECK_IN_OPENS_BEFORE,
    OpeningHours,
    Rules,
    RuleViolationError,
    Window,
    check_window,
    closed_windows,
    day_window,
    effective_rules,
    expand_recurrence,
    find_conflicts,
    full_windows,
    merge,
    subtract,
)
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import (
    Blackout,
    Booking,
    BookingSeries,
    OpeningHoursRow,
    Resource,
    ResourceType,
    as_utc,
    iso,
)

MODULE = "facility-booking"
RESOURCE_READ = f"{MODULE}:resource:read"
RESOURCE_MANAGE = f"{MODULE}:resource:manage"
BOOKING_READ = f"{MODULE}:booking:read"
BOOKING_READ_ALL = f"{MODULE}:booking:read-all"
BOOKING_CREATE = f"{MODULE}:booking:create"
BOOKING_APPROVE = f"{MODULE}:booking:approve"
BOOKING_MANAGE = f"{MODULE}:booking:manage"
MAX_AVAILABILITY_DAYS = 31


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class BookingError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message, ...})."""

    def __init__(self, status: int, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


def _not_found(what: str) -> BookingError:
    return BookingError(404, "not_found", f"{what} not found in your organisation")


def _forbidden(message: str) -> BookingError:
    return BookingError(403, "forbidden", message)


def _rule_error(v: RuleViolationError) -> BookingError:
    extra = {"rule": v.rule} if v.rule else {}
    if v.limit is not None:
        extra["limit"] = v.limit
    return BookingError(422, v.code, v.message, **extra)


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


# ---------------------------------------------------------------- serialisation


def resource_type_dict(t: ResourceType, resource_count: int | None = None) -> dict:
    d = {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "name": t.name,
        "description": t.description,
        "colour": t.colour,
        "default_rules": dict(t.default_rules or {}),
        "created_at": iso(t.created_at),
    }
    if resource_count is not None:
        d["resource_count"] = resource_count
    return d


def _rules_for(db: Session, resource: Resource, settings: ModuleSettings) -> Rules:
    rtype = repo.get(db, ResourceType, resource.type_id)
    return effective_rules(settings.default_rules(), rtype.default_rules if rtype else None, resource.rules)


def opening_dict(row: OpeningHoursRow | OpeningHours) -> dict:
    return {"weekday": row.weekday, "opens": row.opens, "closes": row.closes}


def resource_dict(db: Session, r: Resource, settings: ModuleSettings | None = None) -> dict:
    settings = settings or load_settings()
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "type_id": r.type_id,
        "name": r.name,
        "code": r.code,
        "location": r.location,
        "capacity": r.capacity,
        "description": r.description,
        "attributes": dict(r.attributes or {}),
        "image_document_id": r.image_document_id,
        "approver_user_ids": list(r.approver_user_ids or []),
        "rules": dict(r.rules or {}),
        "status": r.status,
        "effective_rules": _rules_for(db, r, settings).to_dict(),
        "opening_hours": [opening_dict(o) for o in repo.opening_hours(db, r.id)],
        "created_at": iso(r.created_at),
        "updated_at": iso(r.updated_at),
    }


def blackout_dict(b: Blackout) -> dict:
    return {
        "id": b.id,
        "organisation_id": b.organisation_id,
        "resource_id": b.resource_id,
        "start_at": iso(b.start_at),
        "end_at": iso(b.end_at),
        "reason": b.reason,
        "created_by": b.created_by,
    }


def _is_booker(actor: Actor, b: Booking) -> bool:
    return actor.user_id in (b.booked_by, b.booked_for)


def _is_approver(actor: Actor, resource: Resource | None) -> bool:
    return bool(resource) and actor.user_id in (resource.approver_user_ids or []) and actor.can(BOOKING_APPROVE)


def allowed_actions(
    actor: Actor, b: Booking, resource: Resource | None, now: datetime, grace_minutes: int
) -> list[str]:
    start, end = as_utc(b.start_at), as_utc(b.end_at)
    manage = actor.can(BOOKING_MANAGE)
    own_future = _is_booker(actor, b) and start > now
    can: list[str] = []
    if b.status in CHANGEABLE_STATUSES and (manage or own_future):
        can += ["edit", "cancel"]
    if b.status == "pending" and (manage or _is_approver(actor, resource)):
        can += ["approve", "reject"]
    in_window = start - CHECK_IN_OPENS_BEFORE <= now <= start + timedelta(minutes=grace_minutes) and now < end
    if b.status == "confirmed" and in_window and (manage or _is_booker(actor, b)):
        can.append("check_in")
    if b.status == "confirmed" and manage and now >= start:
        can.append("no_show")
    return can


def booking_dict(
    b: Booking,
    resource: Resource | None,
    actor: Actor,
    now: datetime | None = None,
    settings: ModuleSettings | None = None,
) -> dict:
    settings = settings or load_settings()
    now = now or clock()
    return {
        "id": b.id,
        "organisation_id": b.organisation_id,
        "resource_id": b.resource_id,
        "resource_name": resource.name if resource else None,
        "resource_type_id": resource.type_id if resource else None,
        "series_id": b.series_id,
        "start_at": iso(b.start_at),
        "end_at": iso(b.end_at),
        "status": b.status,
        "title": b.title,
        "notes": b.notes,
        "party_size": b.party_size,
        "booked_by": b.booked_by,
        "booked_for": b.booked_for,
        "source": b.source,
        "decided_by": b.decided_by,
        "decided_at": iso(b.decided_at),
        "decision_note": b.decision_note,
        "cancelled_by": b.cancelled_by,
        "cancel_reason": b.cancel_reason,
        "checked_in_at": iso(b.checked_in_at),
        "created_at": iso(b.created_at),
        "updated_at": iso(b.updated_at),
        "can": allowed_actions(actor, b, resource, now, settings.no_show_grace_minutes),
    }


def _event_fields(b: Booking) -> dict:
    return {
        "booking_id": b.id,
        "series_id": b.series_id,
        "resource_id": b.resource_id,
        "booked_by": b.booked_by,
        "booked_for": b.booked_for,
        "start_at": iso(b.start_at),
        "end_at": iso(b.end_at),
        "source": b.source,
    }


# ---------------------------------------------------------------- resource types


def list_resource_types(db: Session) -> list[dict]:
    return [resource_type_dict(t, repo.count_resources_of_type(db, t.id)) for t in repo.resource_types(db)]


def create_resource_type(db: Session, actor: Actor, data: dict) -> dict:
    if repo.resource_type_by_name(db, data["name"]):
        raise BookingError(409, "name_taken", "a resource type with this name already exists")
    t = ResourceType(organisation_id=actor.organisation_id, **data)
    db.add(t)
    db.commit()
    return resource_type_dict(t, 0)


def update_resource_type(db: Session, actor: Actor, type_id: str, data: dict) -> dict:
    t = repo.get(db, ResourceType, type_id)
    if t is None:
        raise _not_found("resource type")
    if "name" in data and data["name"] != t.name and repo.resource_type_by_name(db, data["name"]):
        raise BookingError(409, "name_taken", "a resource type with this name already exists")
    for key, value in data.items():
        setattr(t, key, value)
    db.commit()
    return resource_type_dict(t, repo.count_resources_of_type(db, t.id))


def delete_resource_type(db: Session, actor: Actor, type_id: str) -> None:
    t = repo.get(db, ResourceType, type_id)
    if t is None:
        raise _not_found("resource type")
    if repo.count_resources_of_type(db, type_id):
        raise BookingError(409, "type_in_use", "resources still use this type")
    db.delete(t)
    db.commit()


# ---------------------------------------------------------------- resources


def _resource_or_404(db: Session, resource_id: str) -> Resource:
    r = repo.get(db, Resource, resource_id)
    if r is None:
        raise _not_found("resource")
    return r


def list_resources(db: Session, actor: Actor, filters: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    items = repo.resources(db)
    if filters.get("type_id"):
        items = [r for r in items if r.type_id == filters["type_id"]]
    if filters.get("status"):
        items = [r for r in items if r.status == filters["status"]]
    if filters.get("min_capacity"):
        items = [r for r in items if (r.capacity or 0) >= filters["min_capacity"]]
    if filters.get("q"):
        needle = filters["q"].lower()
        items = [r for r in items if needle in _search_text(r)]
    if filters.get("free_from") and filters.get("free_to"):
        window = Window(as_utc(filters["free_from"]), as_utc(filters["free_to"]))
        items = [r for r in items if _is_free(db, r, window, settings)]
    total = len(items)
    chunk = items[(page - 1) * page_size : page * page_size]
    return {
        "items": [resource_dict(db, r, settings) for r in chunk],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _search_text(r: Resource) -> str:
    parts = [r.name, r.code or "", r.location or "", *[f"{k} {v}" for k, v in (r.attributes or {}).items()]]
    return " ".join(parts).lower()


def _is_free(db: Session, r: Resource, window: Window, settings: ModuleSettings) -> bool:
    if r.status != "active":
        return False
    rules = _rules_for(db, r, settings)
    existing = [
        Window(as_utc(b.start_at), as_utc(b.end_at)) for b in repo.active_bookings(db, r.id, window.start, window.end)
    ]
    if find_conflicts(
        window, existing, buffer_minutes=rules.buffer_minutes, max_concurrent=rules.max_concurrent_bookings
    ):
        return False
    if any(window.overlaps(b) for b in repo.blackout_windows(db, r.id, window.start, window.end)):
        return False
    return not closed_windows(window, repo.opening_rules(db, r.id), settings.tz)


def create_resource(db: Session, actor: Actor, data: dict) -> dict:
    if repo.get(db, ResourceType, data["type_id"]) is None:
        raise _not_found("resource type")
    if data.get("code") and repo.resource_by_code(db, data["code"]):
        raise BookingError(409, "code_taken", "a resource with this code already exists")
    r = Resource(organisation_id=actor.organisation_id, status="active", **data)
    db.add(r)
    db.flush()
    _publish(
        db,
        actor,
        "resource.created",
        actor.organisation_id,
        {"resource_id": r.id, "type_id": r.type_id, "name": r.name, "capacity": r.capacity},
    )
    db.commit()
    return resource_dict(db, r)


def get_resource(db: Session, resource_id: str) -> dict:
    return resource_dict(db, _resource_or_404(db, resource_id))


def update_resource(db: Session, actor: Actor, resource_id: str, data: dict) -> dict:
    r = _resource_or_404(db, resource_id)
    if "type_id" in data and repo.get(db, ResourceType, data["type_id"]) is None:
        raise _not_found("resource type")
    if data.get("code") and data["code"] != r.code and repo.resource_by_code(db, data["code"]):
        raise BookingError(409, "code_taken", "a resource with this code already exists")
    changed = [k for k, v in data.items() if getattr(r, k) != v]
    for key in changed:
        setattr(r, key, data[key])
    if changed:
        _publish(db, actor, "resource.updated", r.organisation_id, {"resource_id": r.id, "changed": changed})
    db.commit()
    return resource_dict(db, r)


def _future_active(db: Session, resource_id: str, start: datetime, end: datetime | None = None) -> list[Booking]:
    return repo.active_bookings(db, resource_id, start, end or datetime.max.replace(tzinfo=start.tzinfo))


def set_resource_status(db: Session, actor: Actor, resource_id: str, status: str, reason: str | None) -> dict:
    r = _resource_or_404(db, resource_id)
    now = clock()
    affected = _future_active(db, r.id, now) if status != "active" else []
    previous, r.status = r.status, status
    if previous != status:
        _publish(
            db,
            actor,
            "resource.status-changed",
            r.organisation_id,
            {
                "resource_id": r.id,
                "from": previous,
                "to": status,
                "reason": reason,
                "affected_booking_ids": [b.id for b in affected],
            },
        )
    db.commit()
    return {"resource": resource_dict(db, r), "affected_bookings": [booking_dict(b, r, actor, now) for b in affected]}


def set_opening_hours(db: Session, actor: Actor, resource_id: str, hours: list[dict]) -> list[dict]:
    r = _resource_or_404(db, resource_id)
    for row in repo.opening_hours(db, r.id):
        db.delete(row)
    for h in hours:
        db.add(OpeningHoursRow(organisation_id=r.organisation_id, resource_id=r.id, **h))
    _publish(db, actor, "resource.updated", r.organisation_id, {"resource_id": r.id, "changed": ["opening_hours"]})
    db.commit()
    return [opening_dict(o) for o in repo.opening_hours(db, r.id)]


def list_blackouts(db: Session, resource_id: str, start: datetime | None, end: datetime | None) -> list[dict]:
    r = _resource_or_404(db, resource_id)
    return [blackout_dict(b) for b in repo.blackouts(db, r.id, as_utc(start), as_utc(end))]


def add_blackout(db: Session, actor: Actor, resource_id: str, data: dict) -> dict:
    r = _resource_or_404(db, resource_id)
    start, end = as_utc(data["start_at"]), as_utc(data["end_at"])
    if end <= start:
        raise BookingError(422, "invalid_window", "end must be after start")
    b = Blackout(
        organisation_id=r.organisation_id,
        resource_id=r.id,
        start_at=start,
        end_at=end,
        reason=data["reason"],
        created_by=actor.user_id,
    )
    db.add(b)
    db.flush()
    affected = repo.active_bookings(db, r.id, start, end)
    _publish(
        db,
        actor,
        "blackout.created",
        r.organisation_id,
        {
            "blackout_id": b.id,
            "resource_id": r.id,
            "start_at": iso(start),
            "end_at": iso(end),
            "reason": b.reason,
            "affected_booking_ids": [x.id for x in affected],
        },
    )
    db.commit()
    now = clock()
    return {"blackout": blackout_dict(b), "affected_bookings": [booking_dict(x, r, actor, now) for x in affected]}


def delete_blackout(db: Session, actor: Actor, blackout_id: str) -> None:
    b = repo.get(db, Blackout, blackout_id)
    if b is None:
        raise _not_found("blackout")
    _publish(db, actor, "resource.updated", b.organisation_id, {"resource_id": b.resource_id, "changed": ["blackouts"]})
    db.delete(b)
    db.commit()


def availability(db: Session, actor: Actor, resource_id: str, start: datetime, end: datetime) -> dict:
    r = _resource_or_404(db, resource_id)
    span = Window(as_utc(start), as_utc(end))
    if span.end <= span.start:
        raise BookingError(422, "invalid_window", "to must be after from")
    if span.end - span.start > timedelta(days=MAX_AVAILABILITY_DAYS):
        raise BookingError(422, "invalid_window", f"at most {MAX_AVAILABILITY_DAYS} days", limit=MAX_AVAILABILITY_DAYS)
    settings = load_settings()
    rules = _rules_for(db, r, settings)
    bookings = repo.active_bookings(db, r.id, span.start, span.end)
    booking_windows = [Window(as_utc(b.start_at), as_utc(b.end_at)) for b in bookings]
    closed = closed_windows(span, repo.opening_rules(db, r.id), settings.tz)
    blackouts = repo.blackout_windows(db, r.id, span.start, span.end)
    full = full_windows(booking_windows, rules.max_concurrent_bookings)
    reveal = actor.can(BOOKING_READ_ALL)
    busy: list[dict] = [{"start_at": iso(w.start), "end_at": iso(w.end), "kind": "closed"} for w in closed]
    busy += [{"start_at": iso(w.start), "end_at": iso(w.end), "kind": "blackout"} for w in blackouts]
    if rules.max_concurrent_bookings <= 1:
        for b in bookings:
            item = {"start_at": iso(b.start_at), "end_at": iso(b.end_at), "kind": "booking"}
            if reveal:
                item |= {"booking_id": b.id, "title": b.title}
            busy.append(item)
    else:
        busy += [{"start_at": iso(w.start), "end_at": iso(w.end), "kind": "booking"} for w in full]
    if r.status != "active":
        busy.append({"start_at": iso(span.start), "end_at": iso(span.end), "kind": "closed"})
        free = []
    else:
        free = subtract(span, merge([*closed, *blackouts, *full]))
    busy.sort(key=lambda x: x["start_at"])
    return {
        "resource_id": r.id,
        "from": iso(span.start),
        "to": iso(span.end),
        "free": [{"start_at": iso(w.start), "end_at": iso(w.end)} for w in free],
        "busy": busy,
    }


# ---------------------------------------------------------------- bookings


def _check_fits(
    db: Session,
    r: Resource,
    rules: Rules,
    window: Window,
    now: datetime,
    settings: ModuleSettings,
    extra: list[Window] | None = None,
    exclude_id: str | None = None,
) -> list[Window]:
    """Raise BookingError for a rule violation; return clashing windows (empty when it fits)."""
    try:
        check_window(
            window,
            rules,
            now=now,
            opening=repo.opening_rules(db, r.id),
            blackouts=repo.blackout_windows(db, r.id, window.start, window.end),
            tz=settings.tz,
        )
    except RuleViolationError as v:
        raise _rule_error(v) from v
    pad = timedelta(minutes=rules.buffer_minutes)
    existing = repo.active_bookings(db, r.id, window.start - pad, window.end + pad, exclude_id=exclude_id)
    windows = [Window(as_utc(b.start_at), as_utc(b.end_at)) for b in existing] + list(extra or [])
    return find_conflicts(
        window, windows, buffer_minutes=rules.buffer_minutes, max_concurrent=rules.max_concurrent_bookings
    )


def _conflict_error(actor: Actor, db: Session, r: Resource, clashes: list[Window]) -> BookingError:
    reveal = actor.can(BOOKING_READ_ALL)
    items = []
    for w in clashes:
        item = {"start_at": iso(w.start), "end_at": iso(w.end)}
        if reveal:
            match = next(
                (
                    b
                    for b in repo.active_bookings(db, r.id, w.start, w.end)
                    if as_utc(b.start_at) == w.start and as_utc(b.end_at) == w.end
                ),
                None,
            )
            if match:
                item["booking_id"] = match.id
        items.append(item)
    return BookingError(409, "booking_conflict", "the window clashes with existing bookings", conflicts=items)


def create_booking(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    now = clock()
    r = repo.resource_for_update(db, data["resource_id"])
    if r is None:
        raise _not_found("resource")
    if r.status != "active":
        raise BookingError(422, "resource_not_active", "the resource is not taking bookings")
    manage = actor.can(BOOKING_MANAGE)
    booked_for = data.get("booked_for") or actor.user_id
    if booked_for != actor.user_id and not manage:
        raise _forbidden("booking for someone else needs facility-booking:booking:manage")
    rules = _rules_for(db, r, settings)
    if rules.bookable_role_ids and not set(actor.roles) & set(rules.bookable_role_ids) and not manage:
        raise _forbidden("your role may not book this resource")
    party_size = data.get("party_size") or 1
    if r.capacity and party_size > r.capacity:
        raise BookingError(422, "over_capacity", "the party is larger than the resource holds", limit=r.capacity)
    first = Window(as_utc(data["start_at"]), as_utc(data["end_at"]))
    recurrence = data.get("recurrence")
    try:
        windows = (
            [first]
            if not recurrence
            else expand_recurrence(
                first,
                frequency=recurrence["frequency"],
                interval=recurrence.get("interval") or 1,
                weekdays=recurrence.get("weekdays"),
                until=recurrence.get("until"),
                count=recurrence.get("count"),
                limit=settings.max_series_occurrences,
                tz=settings.tz,
            )
        )
    except RuleViolationError as v:
        raise _rule_error(v) from v
    accepted: list[Window] = []
    skipped: list[Window] = []
    for window in windows:
        clashes = _check_fits(db, r, rules, window, now, settings, extra=accepted)
        if not clashes:
            accepted.append(window)
        elif recurrence and data.get("skip_conflicts"):
            skipped.append(window)
        else:
            raise _conflict_error(actor, db, r, clashes)
    if not accepted:
        raise BookingError(
            409,
            "booking_conflict",
            "every occurrence clashes with existing bookings",
            conflicts=[{"start_at": iso(w.start), "end_at": iso(w.end)} for w in skipped],
        )
    series = None
    if recurrence:
        series = BookingSeries(
            organisation_id=r.organisation_id,
            resource_id=r.id,
            booked_by=actor.user_id,
            booked_for=booked_for,
            recurrence=_jsonable(recurrence),
        )
        db.add(series)
        db.flush()
    status = "pending" if rules.requires_approval and not manage else "confirmed"
    created = []
    for window in accepted:
        b = Booking(
            organisation_id=r.organisation_id,
            resource_id=r.id,
            series_id=series.id if series else None,
            start_at=window.start,
            end_at=window.end,
            status=status,
            title=data.get("title"),
            notes=data.get("notes"),
            party_size=party_size,
            booked_by=actor.user_id,
            booked_for=booked_for,
            source=data.get("source"),
        )
        db.add(b)
        db.flush()
        if status == "pending":
            _publish(
                db,
                actor,
                "booking.requested",
                r.organisation_id,
                _event_fields(b) | {"approver_user_ids": list(r.approver_user_ids or [])},
            )
        else:
            _publish(db, actor, "booking.confirmed", r.organisation_id, _event_fields(b) | {"approved_by": None})
        created.append(b)
    db.commit()
    out = [booking_dict(b, r, actor, now, settings) for b in created]
    return {
        "booking": out[0],
        "series_id": series.id if series else None,
        "created": out,
        "skipped": [{"start_at": iso(w.start), "end_at": iso(w.end)} for w in skipped],
    }


def _jsonable(value: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date | datetime) else v) for k, v in value.items()}


def _approver_resource_ids(db: Session, actor: Actor) -> set[str]:
    return {r.id for r in repo.resources(db) if actor.user_id in (r.approver_user_ids or [])}


def _day(value: str | date, tz) -> date:
    if isinstance(value, date):
        return value
    if value == "today":
        return clock().astimezone(tz).date()
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise BookingError(422, "invalid_window", "date must be YYYY-MM-DD or 'today'") from e


def _time_range(settings: ModuleSettings, day: str | None, start: str | datetime | None, end: datetime | None):
    if day:
        w = day_window(_day(day, settings.tz), settings.tz)
        return w.start, w.end
    if start == "now":
        start = clock()
    elif isinstance(start, str):
        try:
            start = datetime.fromisoformat(start)
        except ValueError as e:
            raise BookingError(422, "invalid_window", "from must be a date-time or 'now'") from e
    return as_utc(start), as_utc(end)


def _visible(db: Session, actor: Actor, scope: str) -> Callable[[Booking], bool]:
    if scope == "mine":
        return lambda b: _is_booker(actor, b)
    if actor.can(BOOKING_READ_ALL):
        return lambda b: True
    approver_of = _approver_resource_ids(db, actor)
    return lambda b: b.resource_id in approver_of


def list_bookings(db: Session, actor: Actor, q: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    now = clock()
    start, end = _time_range(settings, q.get("date"), q.get("from"), q.get("to"))
    visible = _visible(db, actor, q.get("scope") or "mine")
    items = [b for b in repo.bookings_between(db, start, end) if visible(b)]
    if q.get("resource_id"):
        items = [b for b in items if b.resource_id == q["resource_id"]]
    resources = {r.id: r for r in repo.resources(db)}
    if q.get("type_id"):
        items = [b for b in items if resources.get(b.resource_id) and resources[b.resource_id].type_id == q["type_id"]]
    if q.get("status"):
        items = [b for b in items if b.status in set(q["status"])]
    if q.get("source_module"):
        items = [b for b in items if (b.source or {}).get("module") == q["source_module"]]
    total = len(items)
    chunk = items[(page - 1) * page_size : page * page_size]
    return {
        "items": [booking_dict(b, resources.get(b.resource_id), actor, now, settings) for b in chunk],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _booking_for(db: Session, actor: Actor, booking_id: str) -> tuple[Booking, Resource | None]:
    b = repo.get(db, Booking, booking_id)
    if b is None:
        raise _not_found("booking")
    r = repo.get(db, Resource, b.resource_id)
    if not (
        _is_booker(actor, b)
        or actor.can(BOOKING_READ_ALL)
        or actor.can(BOOKING_MANAGE)
        or (r and actor.user_id in (r.approver_user_ids or []))
    ):
        raise _not_found("booking")
    return b, r


def get_booking(db: Session, actor: Actor, booking_id: str) -> dict:
    b, r = _booking_for(db, actor, booking_id)
    return booking_dict(b, r, actor)


def update_booking(db: Session, actor: Actor, booking_id: str, data: dict) -> dict:
    settings = load_settings()
    now = clock()
    b, r = _booking_for(db, actor, booking_id)
    if "edit" not in allowed_actions(actor, b, r, now, settings.no_show_grace_minutes):
        if b.status not in CHANGEABLE_STATUSES:
            raise BookingError(409, "not_changeable", f"a {b.status} booking cannot be changed")
        raise _forbidden("only the booker, before it starts, or a manager may change this booking")
    target = repo.resource_for_update(db, data.get("resource_id") or b.resource_id)
    if target is None:
        raise _not_found("resource")
    if target.status != "active":
        raise BookingError(422, "resource_not_active", "the resource is not taking bookings")
    old = {"resource_id": b.resource_id, "start_at": iso(b.start_at), "end_at": iso(b.end_at)}
    window = Window(as_utc(data.get("start_at") or b.start_at), as_utc(data.get("end_at") or b.end_at))
    moved = target.id != b.resource_id or iso(window.start) != old["start_at"] or iso(window.end) != old["end_at"]
    party_size = data.get("party_size") or b.party_size
    if target.capacity and party_size > target.capacity:
        raise BookingError(422, "over_capacity", "the party is larger than the resource holds", limit=target.capacity)
    rules = _rules_for(db, target, settings)
    if moved:
        clashes = _check_fits(db, target, rules, window, now, settings, exclude_id=b.id)
        if clashes:
            raise _conflict_error(actor, db, target, clashes)
    for key in ("title", "notes"):
        if key in data:
            setattr(b, key, data[key])
    b.party_size = party_size
    if moved:
        b.resource_id, b.start_at, b.end_at = target.id, window.start, window.end
        if rules.requires_approval and not actor.can(BOOKING_MANAGE):
            b.status = "pending"
        _publish(
            db,
            actor,
            "booking.rescheduled",
            b.organisation_id,
            {
                "booking_id": b.id,
                "from_resource_id": old["resource_id"],
                "to_resource_id": target.id,
                "from_start_at": old["start_at"],
                "from_end_at": old["end_at"],
                "start_at": iso(window.start),
                "end_at": iso(window.end),
                "status": b.status,
                "source": b.source,
            },
        )
    db.commit()
    return booking_dict(b, target, actor, now, settings)


def decide_booking(db: Session, actor: Actor, booking_id: str, approve: bool, note: str | None) -> dict:
    now = clock()
    b, r = _booking_for(db, actor, booking_id)
    if not (actor.can(BOOKING_MANAGE) or _is_approver(actor, r)):
        raise _forbidden("only an approver of this resource or a manager may decide")
    if b.status != "pending":
        raise BookingError(409, "not_pending", "the booking is not pending")
    b.decided_by, b.decided_at, b.decision_note = actor.user_id, now, note
    if approve:
        b.status = "confirmed"
        _publish(db, actor, "booking.confirmed", b.organisation_id, _event_fields(b) | {"approved_by": actor.user_id})
    else:
        b.status = "rejected"
        _publish(
            db,
            actor,
            "booking.rejected",
            b.organisation_id,
            {
                "booking_id": b.id,
                "resource_id": b.resource_id,
                "booked_by": b.booked_by,
                "booked_for": b.booked_for,
                "rejected_by": actor.user_id,
                "reason": note,
                "source": b.source,
            },
        )
    db.commit()
    return booking_dict(b, r, actor, now)


def _cancel(db: Session, actor: Actor, b: Booking, reason: str | None) -> None:
    b.status, b.cancelled_by, b.cancel_reason = "cancelled", actor.user_id, reason
    _publish(
        db,
        actor,
        "booking.cancelled",
        b.organisation_id,
        {
            "booking_id": b.id,
            "series_id": b.series_id,
            "resource_id": b.resource_id,
            "booked_by": b.booked_by,
            "booked_for": b.booked_for,
            "cancelled_by": actor.user_id,
            "reason": reason,
            "start_at": iso(b.start_at),
            "source": b.source,
        },
    )


def cancel_booking(db: Session, actor: Actor, booking_id: str, reason: str | None) -> dict:
    now = clock()
    b, r = _booking_for(db, actor, booking_id)
    if b.status not in CHANGEABLE_STATUSES:
        raise BookingError(409, "not_cancellable", f"a {b.status} booking cannot be cancelled")
    manage = actor.can(BOOKING_MANAGE)
    if not manage and not (_is_booker(actor, b) and as_utc(b.start_at) > now):
        raise BookingError(409, "already_started", "only a manager can cancel a booking that has started")
    if manage and not _is_booker(actor, b) and not reason:
        raise BookingError(422, "reason_required", "a manager cancelling someone else's booking must give a reason")
    _cancel(db, actor, b, reason)
    db.commit()
    return booking_dict(b, r, actor, now)


def check_in(db: Session, actor: Actor, booking_id: str) -> dict:
    settings = load_settings()
    now = clock()
    b, r = _booking_for(db, actor, booking_id)
    if not (_is_booker(actor, b) or actor.can(BOOKING_MANAGE)):
        raise _forbidden("only the booker or a manager may check in")
    if "check_in" not in allowed_actions(actor, b, r, now, settings.no_show_grace_minutes):
        raise BookingError(409, "outside_check_in_window", "outside the check-in window or not confirmed")
    b.status, b.checked_in_at = "checked_in", now
    _publish(
        db,
        actor,
        "booking.checked-in",
        b.organisation_id,
        {
            "booking_id": b.id,
            "resource_id": b.resource_id,
            "booked_for": b.booked_for,
            "checked_in_at": iso(now),
        },
    )
    db.commit()
    return booking_dict(b, r, actor, now, settings)


def _mark_no_show(db: Session, actor: Actor | None, b: Booking, recorded_by: str) -> None:
    b.status = "no_show"
    _publish(
        db,
        actor,
        "booking.no-show-recorded",
        b.organisation_id,
        {
            "booking_id": b.id,
            "resource_id": b.resource_id,
            "booked_for": b.booked_for,
            "start_at": iso(b.start_at),
            "recorded_by": recorded_by,
        },
    )


def record_no_show(db: Session, actor: Actor, booking_id: str) -> dict:
    now = clock()
    b, r = _booking_for(db, actor, booking_id)
    if b.status != "confirmed" or now < as_utc(b.start_at):
        raise BookingError(409, "not_started", "the booking has not started or is not confirmed")
    _mark_no_show(db, actor, b, actor.user_id)
    db.commit()
    return booking_dict(b, r, actor, now)


def cancel_series(db: Session, actor: Actor, series_id: str, reason: str | None) -> list[dict]:
    now = clock()
    s = repo.get(db, BookingSeries, series_id)
    if s is None:
        raise _not_found("series")
    manage = actor.can(BOOKING_MANAGE)
    if not manage and actor.user_id not in (s.booked_by, s.booked_for):
        raise _forbidden("only the booker or a manager may cancel this series")
    r = repo.get(db, Resource, s.resource_id)
    cancelled = []
    for b in repo.series_bookings(db, s.id):
        if b.status in CHANGEABLE_STATUSES and as_utc(b.start_at) > now:
            _cancel(db, actor, b, reason)
            cancelled.append(b)
    db.commit()
    return [booking_dict(b, r, actor, now) for b in cancelled]


def summary(db: Session, actor: Actor, day: str | None) -> dict:
    settings = load_settings()
    now = clock()
    w = day_window(_day(day or "today", settings.tz), settings.tz)
    visible = _visible(db, actor, "managed")
    todays = [b for b in repo.bookings_between(db, w.start, w.end) if visible(b)]
    pending = [b for b in repo.bookings_between(db, None, None) if visible(b) and b.status == "pending"]
    managed_ids = None if actor.can(BOOKING_READ_ALL) else _approver_resource_ids(db, actor)
    out_of_service = [
        r for r in repo.resources(db) if r.status != "active" and (managed_ids is None or r.id in managed_ids)
    ]
    return {
        "date": w.start.astimezone(settings.tz).date().isoformat(),
        "bookings_today": sum(1 for b in todays if b.status not in ("cancelled", "rejected")),
        "pending_approval": len(pending),
        "checked_in_now": sum(
            1 for b in todays if b.status == "checked_in" and as_utc(b.start_at) <= now < as_utc(b.end_at)
        ),
        "no_shows_today": sum(1 for b in todays if b.status == "no_show"),
        "resources_out_of_service": len(out_of_service),
    }
