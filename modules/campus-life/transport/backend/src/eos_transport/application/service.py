"""Use cases of transport (docs/prd.md, docs/user-stories.md). Each one checks the domain rules, changes state, writes
an audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same transaction.
Positions are high volume: they are stored and purged, never published or audited one by one.

A person is identified by their identity user id (the token subject). A caller drives a route when a driver record
with their person_id is the route's current driver."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import PASS_TRANSITIONS, RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AuditEntry,
    Driver,
    Notice,
    Pass,
    Position,
    Route,
    RouteStop,
    Stop,
    Trip,
    Vehicle,
    as_utc,
    iso,
)

MODULE = "transport"
ROUTE_READ = "transport:route:read"
ROUTE_MANAGE = "transport:route:manage"
VEHICLE_READ = "transport:vehicle:read"
VEHICLE_MANAGE = "transport:vehicle:manage"
PASS_READ = "transport:pass:read"
PASS_MANAGE = "transport:pass:manage"
TRACKING_READ = "transport:tracking:read"
TRACKING_RECORD = "transport:tracking:record"
NOTICE_PUBLISH = "transport:notice:publish"
SELF_READ = "transport:self:read"
SELF_REQUEST = "transport:self:request"

# Domain rule code -> HTTP status.
RULE_STATUS = {
    "invalid_status": 409,
    "route_full": 409,
    "vehicle_inactive": 409,
    "driver_inactive": 409,
    "document_expired": 409,
    "invalid_stops": 422,
    "invalid_dates": 422,
    "invalid_delay": 422,
    "reason_required": 422,
}


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().date()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class TransportError(Exception):
    """A refusal with an HTTP status and an error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> TransportError:
    return TransportError(404, "not_found", f"{what} not found in your organisation")


def _conflict(code: str, message: str) -> TransportError:
    return TransportError(409, code, message)


def _rule(v: RuleViolationError) -> TransportError:
    return TransportError(RULE_STATUS.get(v.code, 422), v.code, v.message)


def _audit(db: Session, actor: Actor | None, action: str, entity: str, entity_id: str, organisation_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _check(fn, *args) -> None:
    try:
        fn(*args)
    except RuleViolationError as v:
        raise _rule(v) from v


# ---------------------------------------------------------------- serialisation


def stop_dict(s: Stop) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "name": s.name,
        "latitude": s.latitude,
        "longitude": s.longitude,
    }


def route_dicts(db: Session, routes: list[Route]) -> list[dict]:
    """Routes with their stops in order and the names of the assigned vehicle and driver."""
    stops_of = repo.route_stops(db, [r.id for r in routes])
    names = repo.stops_by_id(db, sorted({rs.stop_id for rss in stops_of.values() for rs in rss}))
    out = []
    for r in routes:
        vehicle = repo.get(db, Vehicle, r.vehicle_id) if r.vehicle_id else None
        driver = repo.get(db, Driver, r.driver_id) if r.driver_id else None
        out.append(
            {
                "id": r.id,
                "organisation_id": r.organisation_id,
                "code": r.code,
                "name": r.name,
                "direction": r.direction,
                "active": r.active,
                "stops": [
                    {
                        "stop_id": rs.stop_id,
                        "stop_name": names[rs.stop_id].name if rs.stop_id in names else None,
                        "sequence": rs.sequence,
                        "scheduled_time": rs.scheduled_time,
                    }
                    for rs in stops_of[r.id]
                ],
                "vehicle_id": r.vehicle_id,
                "vehicle_registration_no": vehicle.registration_no if vehicle else None,
                "driver_id": r.driver_id,
                "driver_name": driver.name if driver else None,
            }
        )
    return out


def route_dict(db: Session, r: Route) -> dict:
    return route_dicts(db, [r])[0]


def vehicle_dict(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "organisation_id": v.organisation_id,
        "registration_no": v.registration_no,
        "type": v.type,
        "capacity": v.capacity,
        "insurance_expires_on": iso(v.insurance_expires_on),
        "fitness_expires_on": iso(v.fitness_expires_on),
        "permit_expires_on": iso(v.permit_expires_on),
        "active": v.active,
    }


def driver_dict(d: Driver) -> dict:
    return {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "person_id": d.person_id,
        "name": d.name,
        "licence_no": d.licence_no,
        "licence_expires_on": iso(d.licence_expires_on),
        "phone": d.phone,
        "active": d.active,
    }


def pass_dict(db: Session, p: Pass) -> dict:
    route = repo.get(db, Route, p.route_id)
    stop = repo.get(db, Stop, p.stop_id)
    return {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "person_id": p.person_id,
        "person_name": p.person_name,
        "rider_type": p.rider_type,
        "route_id": p.route_id,
        "route_code": route.code if route else None,
        "stop_id": p.stop_id,
        "stop_name": stop.name if stop else None,
        "valid_from": iso(p.valid_from),
        "valid_to": iso(p.valid_to),
        "status": p.status,
        "decided_by": p.decided_by,
        "reason": p.reason,
    }


def trip_dict(t: Trip) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "route_id": t.route_id,
        "vehicle_id": t.vehicle_id,
        "driver_id": t.driver_id,
        "status": t.status,
        "started_at": iso(t.started_at),
        "ended_at": iso(t.ended_at),
        "delay_minutes": t.delay_minutes,
    }


def position_dict(p: Position) -> dict:
    return {
        "recorded_at": iso(p.recorded_at),
        "latitude": p.latitude,
        "longitude": p.longitude,
        "speed_kmh": p.speed_kmh,
    }


def notice_dict(db: Session, n: Notice) -> dict:
    route = repo.get(db, Route, n.route_id) if n.route_id else None
    return {
        "id": n.id,
        "organisation_id": n.organisation_id,
        "route_id": n.route_id,
        "route_code": route.code if route else None,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "expires_at": iso(n.expires_at),
        "published_at": iso(n.published_at),
        "published_by": n.published_by,
        "status": rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), clock()),
    }


def _page(items: list[dict], next_cursor: str | None) -> dict:
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- stops


def list_stops(db: Session, q: str | None) -> list[dict]:
    return [stop_dict(s) for s in repo.stops(db, q)]


def create_stop(db: Session, actor: Actor, data: dict) -> dict:
    s = Stop(
        organisation_id=actor.organisation_id,
        name=data["name"],
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )
    db.add(s)
    db.flush()
    _audit(db, actor, "stop.created", "stop", s.id, actor.organisation_id)
    db.commit()
    return stop_dict(s)


def update_stop(db: Session, actor: Actor, stop_id: str, data: dict) -> dict:
    s = _get(db, Stop, stop_id, "stop")
    for key in ("name", "latitude", "longitude"):
        if key in data:
            setattr(s, key, data[key])
    _audit(db, actor, "stop.updated", "stop", s.id, s.organisation_id)
    db.commit()
    return stop_dict(s)


# ---------------------------------------------------------------- routes


def list_routes(db: Session, active: bool | None, stop_id: str | None) -> list[dict]:
    return route_dicts(db, repo.routes(db, active, stop_id))


def _checked_stops(db: Session, stops: list[dict]) -> list[dict]:
    try:
        ordered = rules.check_route_stops(stops)
    except RuleViolationError as v:
        raise _rule(v) from v
    found = repo.stops_by_id(db, [s["stop_id"] for s in ordered])
    missing = [s["stop_id"] for s in ordered if s["stop_id"] not in found]
    if missing:
        raise _not_found(f"stop {missing[0]}")
    return ordered


def _set_route_stops(db: Session, route: Route, stops: list[dict]) -> None:
    repo.delete_route_stops(db, route.id)
    for s in stops:
        db.add(
            RouteStop(
                organisation_id=route.organisation_id,
                route_id=route.id,
                stop_id=s["stop_id"],
                sequence=s["sequence"],
                scheduled_time=s.get("scheduled_time"),
            )
        )
    db.flush()


def create_route(db: Session, actor: Actor, data: dict) -> dict:
    if repo.route_by_code(db, data["code"]):
        raise _conflict("route_exists", f"route {data['code']} already exists")
    stops = _checked_stops(db, data["stops"])
    r = Route(
        organisation_id=actor.organisation_id,
        code=data["code"],
        name=data["name"],
        direction=data.get("direction"),
        active=data.get("active", True),
    )
    db.add(r)
    db.flush()
    _set_route_stops(db, r, stops)
    _audit(db, actor, "route.created", "route", r.id, actor.organisation_id)
    db.commit()
    return route_dict(db, r)


def get_route(db: Session, route_id: str) -> dict:
    r = _get(db, Route, route_id, "route")
    vehicle = repo.get(db, Vehicle, r.vehicle_id) if r.vehicle_id else None
    return {
        **route_dict(db, r),
        "capacity": vehicle.capacity if vehicle else None,
        "passes_issued": repo.issued_on_routes(db, [r.id], today()),
    }


def update_route(db: Session, actor: Actor, route_id: str, data: dict) -> dict:
    r = _get(db, Route, route_id, "route")
    if data["code"] != r.code and repo.route_by_code(db, data["code"]):
        raise _conflict("route_exists", f"route {data['code']} already exists")
    stops = _checked_stops(db, data["stops"])
    kept = {s["stop_id"] for s in stops}
    current = [rs.stop_id for rs in repo.route_stops(db, [r.id])[r.id]]
    in_use = repo.issued_at_stop(db, r.id, [sid for sid in current if sid not in kept])
    if in_use:
        raise _conflict("stop_in_use", "a stop being removed is the boarding stop of a current pass or request")
    r.code, r.name = data["code"], data["name"]
    if "direction" in data:
        r.direction = data["direction"]
    if "active" in data and data["active"] is not None:
        if r.active and not data["active"]:
            _audit(db, actor, "route.deactivated", "route", r.id, r.organisation_id)
        r.active = data["active"]
    _set_route_stops(db, r, stops)
    _audit(db, actor, "route.updated", "route", r.id, r.organisation_id)
    db.commit()
    return route_dict(db, r)


def _vehicle_documents(v: Vehicle) -> dict[str, date | None]:
    return {"insurance": v.insurance_expires_on, "fitness": v.fitness_expires_on, "permit": v.permit_expires_on}


def assign_route(db: Session, actor: Actor, route_id: str, vehicle_id: str, driver_id: str) -> dict:
    r = _get(db, Route, route_id, "route")
    v = _get(db, Vehicle, vehicle_id, "vehicle")
    d = _get(db, Driver, driver_id, "driver")
    _check(rules.check_assignable, v.active, _vehicle_documents(v), d.active, d.licence_expires_on, today())
    if (r.vehicle_id, r.driver_id) != (v.id, d.id):
        r.vehicle_id, r.driver_id = v.id, d.id
        _publish(
            db,
            actor,
            "route.reassigned",
            r.organisation_id,
            {"route_id": r.id, "vehicle_id": v.id, "driver_id": d.id},
        )
        _audit(db, actor, "route.reassigned", "route", r.id, r.organisation_id)
    db.commit()
    return route_dict(db, r)


# ---------------------------------------------------------------- vehicles and drivers


def list_vehicles(db: Session, active: bool | None, expiring_within_days: int | None) -> list[dict]:
    rows = repo.vehicles(db, active)
    if expiring_within_days is not None:
        now = today()
        rows = [
            v
            for v in rows
            if any(rules.expires_within(d, now, expiring_within_days) for d in _vehicle_documents(v).values())
        ]
    return [vehicle_dict(v) for v in rows]


def _vehicle_fields(v: Vehicle, data: dict) -> None:
    v.registration_no, v.capacity = data["registration_no"], data["capacity"]
    for key in ("type", "insurance_expires_on", "fitness_expires_on", "permit_expires_on"):
        if key in data:
            setattr(v, key, data[key])
    if data.get("active") is not None:
        v.active = data["active"]


def create_vehicle(db: Session, actor: Actor, data: dict) -> dict:
    if repo.vehicle_by_registration(db, data["registration_no"]):
        raise _conflict("vehicle_exists", f"vehicle {data['registration_no']} already exists")
    v = Vehicle(organisation_id=actor.organisation_id, active=True)
    _vehicle_fields(v, data)
    db.add(v)
    db.flush()
    _audit(db, actor, "vehicle.created", "vehicle", v.id, actor.organisation_id)
    db.commit()
    return vehicle_dict(v)


def update_vehicle(db: Session, actor: Actor, vehicle_id: str, data: dict) -> dict:
    v = _get(db, Vehicle, vehicle_id, "vehicle")
    if data["registration_no"] != v.registration_no and repo.vehicle_by_registration(db, data["registration_no"]):
        raise _conflict("vehicle_exists", f"vehicle {data['registration_no']} already exists")
    for r in repo.routes_with(db, vehicle_id=v.id):
        held = repo.issued_on_routes(db, [r.id], today())
        if data["capacity"] < held:
            raise _conflict(
                "capacity_below_passes", f"route {r.code} has {held} issued passes; capacity {data['capacity']}"
            )
    _vehicle_fields(v, data)
    _audit(db, actor, "vehicle.updated", "vehicle", v.id, v.organisation_id)
    db.commit()
    return vehicle_dict(v)


def list_drivers(db: Session, active: bool | None, expiring_within_days: int | None) -> list[dict]:
    rows = repo.drivers(db, active)
    if expiring_within_days is not None:
        now = today()
        rows = [d for d in rows if rules.expires_within(d.licence_expires_on, now, expiring_within_days)]
    return [driver_dict(d) for d in rows]


def _driver_fields(d: Driver, data: dict) -> None:
    d.name, d.licence_no, d.licence_expires_on = data["name"], data["licence_no"], data["licence_expires_on"]
    for key in ("person_id", "phone"):
        if key in data:
            setattr(d, key, data[key])
    if data.get("active") is not None:
        d.active = data["active"]


def create_driver(db: Session, actor: Actor, data: dict) -> dict:
    d = Driver(organisation_id=actor.organisation_id, active=True)
    _driver_fields(d, data)
    db.add(d)
    db.flush()
    _audit(db, actor, "driver.created", "driver", d.id, actor.organisation_id)
    db.commit()
    return driver_dict(d)


def update_driver(db: Session, actor: Actor, driver_id: str, data: dict) -> dict:
    d = _get(db, Driver, driver_id, "driver")
    _driver_fields(d, data)
    _audit(db, actor, "driver.updated", "driver", d.id, d.organisation_id)
    db.commit()
    return driver_dict(d)


# ---------------------------------------------------------------- passes


def list_passes(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    rows, nxt = repo.page(db, repo.passes_query(db, **filters), cursor, limit)
    return _page([pass_dict(db, p) for p in rows], nxt)


def _bookable(db: Session, route_id: str, stop_id: str, start: date, end: date) -> Route:
    """The route takes a pass at this stop for these dates. Locks the route for the capacity check."""
    route = repo.route_for_update(db, route_id)
    if route is None:
        raise _not_found("route")
    _get(db, Stop, stop_id, "stop")
    if not route.active:
        raise _conflict("route_inactive", f"route {route.code} is inactive")
    if stop_id not in {rs.stop_id for rs in repo.route_stops(db, [route.id])[route.id]}:
        raise _conflict("stop_not_on_route", f"the stop is not on route {route.code}")
    _check(rules.check_pass_period, start, end, today())
    return route


def _check_no_overlap(db: Session, person_id: str, start: date, end: date, exclude_id: str | None = None) -> None:
    for other in repo.blocking_passes(db, person_id, exclude_id):
        if rules.periods_overlap(start, end, other.valid_from, other.valid_to):
            raise _conflict("overlapping_pass", "the person already has a pass or request for these dates")


def _check_seat(db: Session, route: Route, p: Pass, override: bool, reason: str | None) -> None:
    vehicle = repo.get(db, Vehicle, route.vehicle_id) if route.vehicle_id else None
    issued = repo.issued_on_route(db, route.id, p.valid_from, p.valid_to, exclude_id=p.id)
    capacity = vehicle.capacity if vehicle else None
    _check(rules.check_capacity, capacity, issued, override, reason)
    if capacity is None or issued >= capacity:
        p.capacity_override_reason = reason


def _issued(db: Session, actor: Actor, p: Pass) -> None:
    p.decided_by, p.decided_at = actor.user_id, clock()
    _publish(
        db,
        actor,
        "pass.issued",
        p.organisation_id,
        {
            "pass_id": p.id,
            "person_id": p.person_id,
            "rider_type": p.rider_type,
            "route_id": p.route_id,
            "stop_id": p.stop_id,
            "valid_from": iso(p.valid_from),
            "valid_to": iso(p.valid_to),
        },
    )
    _audit(db, actor, "pass.issued", "pass", p.id, p.organisation_id)


def issue_pass(db: Session, actor: Actor, data: dict) -> dict:
    start, end = data["valid_from"], data["valid_to"]
    route = _bookable(db, data["route_id"], data["stop_id"], start, end)
    _check_no_overlap(db, data["person_id"], start, end)
    p = Pass(
        organisation_id=actor.organisation_id,
        person_id=data["person_id"],
        rider_type=data.get("rider_type") or "student",
        route_id=route.id,
        stop_id=data["stop_id"],
        valid_from=start,
        valid_to=end,
        status="issued",
    )
    _check_seat(db, route, p, bool(data.get("override_capacity")), data.get("reason"))
    db.add(p)
    db.flush()
    _issued(db, actor, p)
    db.commit()
    return pass_dict(db, p)


def _pass_transition(p: Pass, action: str) -> None:
    try:
        p.status = rules.transition(PASS_TRANSITIONS, action, p.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def decide_pass(db: Session, actor: Actor, pass_id: str, data: dict) -> dict:
    p = _get(db, Pass, pass_id, "pass")
    if p.status != "requested":
        raise _conflict("invalid_status", f"cannot decide a pass that is {p.status}")
    if data["decision"] == "rejected":
        reason = (data.get("reason") or "").strip()
        if not reason:
            raise TransportError(422, "reason_required", "a reason is required to reject a pass request")
        _pass_transition(p, "reject")
        p.decided_by, p.decided_at, p.reason = actor.user_id, clock(), reason
        _publish(
            db, actor, "pass.rejected", p.organisation_id, {"pass_id": p.id, "person_id": p.person_id, "reason": reason}
        )
        _audit(db, actor, "pass.rejected", "pass", p.id, p.organisation_id)
        db.commit()
        return pass_dict(db, p)
    route = _bookable(db, p.route_id, p.stop_id, p.valid_from, p.valid_to)
    _check_no_overlap(db, p.person_id, p.valid_from, p.valid_to, exclude_id=p.id)
    _check_seat(db, route, p, bool(data.get("override_capacity")), data.get("reason"))
    _pass_transition(p, "issue")
    _issued(db, actor, p)
    db.commit()
    return pass_dict(db, p)


def cancel_pass(db: Session, actor: Actor, pass_id: str, reason: str) -> dict:
    p = _get(db, Pass, pass_id, "pass")
    if not actor.can(PASS_MANAGE) and p.person_id != actor.user_id:
        # transport:self:request covers the caller's own pass only.
        raise _not_found("pass")
    was_issued = p.status == "issued"
    _pass_transition(p, "cancel")
    p.reason, p.cancelled_on = reason, today()
    if was_issued:
        _publish(
            db,
            actor,
            "pass.cancelled",
            p.organisation_id,
            {
                "pass_id": p.id,
                "person_id": p.person_id,
                "route_id": p.route_id,
                "cancelled_on": iso(p.cancelled_on),
                "reason": reason,
            },
        )
    _audit(db, actor, "pass.cancelled", "pass", p.id, p.organisation_id)
    db.commit()
    return pass_dict(db, p)


def request_pass(db: Session, actor: Actor, data: dict) -> dict:
    start, end = data["valid_from"], data["valid_to"]
    route = _bookable(db, data["route_id"], data["stop_id"], start, end)
    _check_no_overlap(db, actor.user_id, start, end)
    p = Pass(
        organisation_id=actor.organisation_id,
        person_id=actor.user_id,
        rider_type="student" if "student" in actor.roles else "staff",
        route_id=route.id,
        stop_id=data["stop_id"],
        valid_from=start,
        valid_to=end,
        status="requested",
    )
    db.add(p)
    db.flush()
    _publish(
        db,
        actor,
        "pass.requested",
        p.organisation_id,
        {
            "pass_id": p.id,
            "person_id": p.person_id,
            "route_id": p.route_id,
            "stop_id": p.stop_id,
            "valid_from": iso(start),
            "valid_to": iso(end),
        },
    )
    _audit(db, actor, "pass.requested", "pass", p.id, p.organisation_id)
    db.commit()
    return pass_dict(db, p)


def _current_first(p: Pass, now: date) -> tuple:
    if rules.pass_covers(p.status, p.valid_from, p.valid_to, now):
        rank = 0
    elif p.status == "issued":
        rank = 1
    elif p.status == "requested":
        rank = 2
    else:
        rank = 3
    return (rank, -p.valid_from.toordinal())


def my_passes(db: Session, actor: Actor) -> list[dict]:
    now = today()
    rows = sorted(repo.person_passes(db, actor.user_id), key=lambda p: _current_first(p, now))
    return [pass_dict(db, p) for p in rows]


# ---------------------------------------------------------------- trips and tracking


def _driver_ids(db: Session, actor: Actor) -> set[str]:
    return {d.id for d in repo.drivers_for_person(db, actor.user_id)}


def _drives(db: Session, actor: Actor, route: Route) -> bool:
    return route.driver_id is not None and route.driver_id in _driver_ids(db, actor)


def start_trip(db: Session, actor: Actor, route_id: str) -> dict:
    route = _get(db, Route, route_id, "route")
    if not _drives(db, actor, route):
        raise _conflict("not_route_driver", "you are not the current driver of this route")
    if not route.active or route.vehicle_id is None:
        raise _conflict("route_not_ready", "the route is inactive or has no vehicle assigned")
    if repo.running_trip(db, route.id) is not None:
        raise _conflict("trip_running", "a trip is already running on this route")
    v = _get(db, Vehicle, route.vehicle_id, "vehicle")
    d = _get(db, Driver, route.driver_id, "driver")
    _check(rules.check_assignable, v.active, _vehicle_documents(v), d.active, d.licence_expires_on, today())
    t = Trip(
        organisation_id=actor.organisation_id,
        route_id=route.id,
        vehicle_id=v.id,
        driver_id=d.id,
        status="running",
        started_at=clock(),
        started_by=actor.user_id,
        delay_minutes=0,
    )
    db.add(t)
    db.flush()
    _publish(
        db,
        actor,
        "trip.started",
        t.organisation_id,
        {
            "trip_id": t.id,
            "route_id": t.route_id,
            "vehicle_id": t.vehicle_id,
            "driver_id": t.driver_id,
            "started_at": iso(t.started_at),
        },
    )
    _audit(db, actor, "trip.started", "trip", t.id, t.organisation_id)
    db.commit()
    return trip_dict(t)


def _running_trip_of(db: Session, actor: Actor, trip_id: str) -> Trip:
    """The caller's trip, running. Only the driver who runs the trip records on it."""
    t = _get(db, Trip, trip_id, "trip")
    if t.driver_id not in _driver_ids(db, actor):
        raise _conflict("not_route_driver", "you are not the driver of this trip")
    if t.status != "running":
        raise _conflict("trip_not_running", "the trip is not running")
    return t


def record_positions(db: Session, actor: Actor, trip_id: str, positions: list[dict]) -> None:
    t = _running_trip_of(db, actor, trip_id)
    for p in positions:
        db.add(
            Position(
                organisation_id=t.organisation_id,
                trip_id=t.id,
                recorded_at=as_utc(p["recorded_at"]),
                latitude=p["latitude"],
                longitude=p["longitude"],
                speed_kmh=p.get("speed_kmh"),
            )
        )
    db.commit()


def report_delay(db: Session, actor: Actor, trip_id: str, delay_minutes: int, note: str | None) -> dict:
    t = _running_trip_of(db, actor, trip_id)
    _check(rules.check_delay, delay_minutes)
    increased = delay_minutes > (t.delay_minutes or 0)
    t.delay_minutes, t.delay_note = delay_minutes, note
    if increased:
        _publish(
            db,
            actor,
            "trip.delayed",
            t.organisation_id,
            {"trip_id": t.id, "route_id": t.route_id, "delay_minutes": delay_minutes},
        )
    _audit(db, actor, "trip.delay_reported", "trip", t.id, t.organisation_id)
    db.commit()
    return trip_dict(t)


def end_trip(db: Session, actor: Actor, trip_id: str) -> dict:
    t = _running_trip_of(db, actor, trip_id)
    t.status, t.ended_at = "completed", clock()
    _publish(
        db,
        actor,
        "trip.completed",
        t.organisation_id,
        {"trip_id": t.id, "route_id": t.route_id, "ended_at": iso(t.ended_at)},
    )
    _audit(db, actor, "trip.completed", "trip", t.id, t.organisation_id)
    db.commit()
    return trip_dict(t)


def live(db: Session, actor: Actor, route_id: str) -> dict | None:
    """Transport staff see every route; a rider sees a route only while holding an issued pass valid today on it."""
    route = _get(db, Route, route_id, "route")
    if not actor.can(TRACKING_READ) and repo.holders_on(db, actor.user_id, route.id, today()) is None:
        raise TransportError(403, "no_pass", "live position needs an issued pass on this route")
    t = repo.running_trip(db, route.id)
    if t is None:
        return None
    last = repo.last_position(db, t.id)
    stops_of = repo.route_stops(db, [route.id])[route.id]
    located = repo.stops_by_id(db, [rs.stop_id for rs in stops_of])
    candidates = [(sid, located[sid].latitude, located[sid].longitude) for sid in (rs.stop_id for rs in stops_of)]
    return {
        **trip_dict(t),
        "last_position": position_dict(last) if last else None,
        "next_stop_id": rules.nearest_stop((last.latitude, last.longitude) if last else None, candidates),
    }


# ---------------------------------------------------------------- notices


def list_notices(db: Session, route_id: str | None) -> list[dict]:
    return [notice_dict(db, n) for n in repo.notices(db, route_id)]


def publish_notice(db: Session, actor: Actor, data: dict) -> dict:
    route_id = data.get("route_id")
    if route_id:
        route = _get(db, Route, route_id, "route")
    if not actor.can(NOTICE_PUBLISH):
        # A driver (tracking:record) publishes only to the route they drive.
        if not route_id or not _drives(db, actor, route):
            raise TransportError(403, "forbidden", "a driver may publish only to the route they drive")
    expires = as_utc(data.get("expires_at"))
    if expires is not None and expires <= clock():
        raise TransportError(422, "invalid_dates", "expires_at must be in the future")
    n = Notice(
        organisation_id=actor.organisation_id,
        route_id=route_id,
        kind=data["kind"],
        title=data["title"],
        body=data["body"],
        expires_at=expires,
        published_at=clock(),
        published_by=actor.user_id,
    )
    db.add(n)
    db.flush()
    _publish(
        db,
        actor,
        "notice.published",
        n.organisation_id,
        {"notice_id": n.id, "route_id": n.route_id, "kind": n.kind, "title": n.title},
    )
    _audit(db, actor, "notice.published", "notice", n.id, n.organisation_id)
    db.commit()
    return notice_dict(db, n)


def withdraw_notice(db: Session, actor: Actor, notice_id: str) -> dict:
    n = _get(db, Notice, notice_id, "notice")
    status = rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), clock())
    if status != "current":
        raise _conflict("invalid_status", f"cannot withdraw a notice that is {status}")
    n.withdrawn_at, n.withdrawn_by = clock(), actor.user_id
    _audit(db, actor, "notice.withdrawn", "notice", n.id, n.organisation_id)
    db.commit()
    return notice_dict(db, n)


def my_notices(db: Session, actor: Actor, limit: int) -> list[dict]:
    """Notices to all routes plus notices to the routes of the caller's issued passes that have not ended."""
    now_day, now = today(), clock()
    route_ids = {
        p.route_id for p in repo.person_passes(db, actor.user_id) if p.status == "issued" and p.valid_to >= now_day
    }
    out = []
    for n in repo.candidate_notices_for(db, route_ids):
        if not rules.notice_visible_to(n.route_id, route_ids):
            continue
        if rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), now) != "current":
            continue
        out.append(notice_dict(db, n))
        if len(out) >= limit:
            break
    return out
