"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security
enforces the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date, datetime

from eos_core.db import scoped
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from ..domain.rules import PASS_BLOCKING
from .models import Driver, Notice, Pass, Position, Route, RouteStop, Stop, Trip, Vehicle


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def route_for_update(db: Session, route_id: str) -> Route | None:
    """Lock the route so two passes issued on it run one after the other and capacity is never exceeded."""
    return db.scalars(_scoped(db, Route).where(Route.id == route_id).with_for_update()).first()


# ---------------------------------------------------------------- pagination

MAX_LIMIT = 100


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(int(base64.urlsafe_b64decode(cursor.encode()).decode()), 0)
    except (ValueError, UnicodeDecodeError):
        return 0


def page(db: Session, query: Select, cursor: str | None, limit: int) -> tuple[list, str | None]:
    offset = decode_cursor(cursor)
    rows = list(db.scalars(query.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    return rows[:limit], encode_cursor(offset + limit) if more else None


# ---------------------------------------------------------------- stops and routes


def stops(db: Session, q: str | None = None) -> list[Stop]:
    query = _scoped(db, Stop)
    if q:
        query = query.where(func.lower(Stop.name).contains(q.lower()))
    return list(db.scalars(query.order_by(Stop.name, Stop.id)))


def stops_by_id(db: Session, ids: list[str]) -> dict[str, Stop]:
    if not ids:
        return {}
    return {s.id: s for s in db.scalars(_scoped(db, Stop).where(Stop.id.in_(ids)))}


def routes(db: Session, active: bool | None = None, stop_id: str | None = None) -> list[Route]:
    q = _scoped(db, Route)
    if active is not None:
        q = q.where(Route.active.is_(active))
    if stop_id:
        serving = _scoped(db, RouteStop).where(RouteStop.stop_id == stop_id).with_only_columns(RouteStop.route_id)
        q = q.where(Route.id.in_(serving))
    return list(db.scalars(q.order_by(Route.code, Route.id)))


def route_by_code(db: Session, code: str) -> Route | None:
    return db.scalars(_scoped(db, Route).where(Route.code == code)).first()


def route_stops(db: Session, route_ids: list[str]) -> dict[str, list[RouteStop]]:
    """Stops of each route, in sequence."""
    out: dict[str, list[RouteStop]] = {rid: [] for rid in route_ids}
    if not route_ids:
        return out
    q = _scoped(db, RouteStop).where(RouteStop.route_id.in_(route_ids)).order_by(RouteStop.sequence)
    for rs in db.scalars(q):
        out[rs.route_id].append(rs)
    return out


def delete_route_stops(db: Session, route_id: str) -> None:
    """Route stops are the route's own ordering, not a record of their own: they are replaced, not kept."""
    for rs in route_stops(db, [route_id])[route_id]:
        db.delete(rs)
    db.flush()


def routes_with(db: Session, vehicle_id: str | None = None, driver_id: str | None = None) -> list[Route]:
    q = _scoped(db, Route)
    if vehicle_id:
        q = q.where(Route.vehicle_id == vehicle_id)
    if driver_id:
        q = q.where(Route.driver_id == driver_id)
    return list(db.scalars(q))


# ---------------------------------------------------------------- vehicles and drivers


def vehicles(db: Session, active: bool | None = None) -> list[Vehicle]:
    q = _scoped(db, Vehicle)
    if active is not None:
        q = q.where(Vehicle.active.is_(active))
    return list(db.scalars(q.order_by(Vehicle.registration_no, Vehicle.id)))


def vehicle_by_registration(db: Session, registration_no: str) -> Vehicle | None:
    return db.scalars(_scoped(db, Vehicle).where(Vehicle.registration_no == registration_no)).first()


def drivers(db: Session, active: bool | None = None) -> list[Driver]:
    q = _scoped(db, Driver)
    if active is not None:
        q = q.where(Driver.active.is_(active))
    return list(db.scalars(q.order_by(Driver.name, Driver.id)))


def drivers_for_person(db: Session, person_id: str) -> list[Driver]:
    return list(db.scalars(_scoped(db, Driver).where(Driver.person_id == person_id, Driver.active.is_(True))))


def all_vehicles(db: Session) -> list[Vehicle]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    return list(db.scalars(select(Vehicle).where(Vehicle.active.is_(True))))


def all_drivers(db: Session) -> list[Driver]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    return list(db.scalars(select(Driver).where(Driver.active.is_(True))))


# ---------------------------------------------------------------- passes


def passes_query(
    db: Session, status: str | None = None, route_id: str | None = None, person_id: str | None = None
) -> Select:
    q = _scoped(db, Pass)
    if status:
        q = q.where(Pass.status == status)
    if route_id:
        q = q.where(Pass.route_id == route_id)
    if person_id:
        q = q.where(Pass.person_id == person_id)
    return q.order_by(Pass.created_at.desc(), Pass.id)


def person_passes(db: Session, person_id: str) -> list[Pass]:
    return list(db.scalars(passes_query(db, person_id=person_id)))


def blocking_passes(db: Session, person_id: str, exclude_id: str | None = None) -> list[Pass]:
    q = _scoped(db, Pass).where(Pass.person_id == person_id, Pass.status.in_(PASS_BLOCKING))
    if exclude_id:
        q = q.where(Pass.id != exclude_id)
    return list(db.scalars(q))


def issued_on_route(db: Session, route_id: str, start: date, end: date, exclude_id: str | None = None) -> int:
    """Issued passes on the route whose period overlaps start..end: the seats taken for that period."""
    q = _scoped(db, Pass).where(
        Pass.route_id == route_id, Pass.status == "issued", Pass.valid_from <= end, Pass.valid_to >= start
    )
    if exclude_id:
        q = q.where(Pass.id != exclude_id)
    return len(list(db.scalars(q)))


def issued_on_routes(db: Session, route_ids: list[str], on: date) -> int:
    """Issued passes valid on `on` across these routes (the seats a vehicle carries today)."""
    if not route_ids:
        return 0
    q = _scoped(db, Pass).where(
        Pass.route_id.in_(route_ids), Pass.status == "issued", Pass.valid_from <= on, Pass.valid_to >= on
    )
    return len(list(db.scalars(q)))


def issued_at_stop(db: Session, route_id: str, stop_ids: list[str]) -> list[Pass]:
    if not stop_ids:
        return []
    q = _scoped(db, Pass).where(Pass.route_id == route_id, Pass.stop_id.in_(stop_ids), Pass.status.in_(PASS_BLOCKING))
    return list(db.scalars(q))


def holders_on(db: Session, person_id: str, route_id: str, on: date) -> Pass | None:
    """The person's issued pass on this route valid on `on`, if any."""
    q = _scoped(db, Pass).where(
        Pass.person_id == person_id,
        Pass.route_id == route_id,
        Pass.status == "issued",
        Pass.valid_from <= on,
        Pass.valid_to >= on,
    )
    return db.scalars(q).first()


def issued_past_end(db: Session, today: date) -> list[Pass]:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    return list(db.scalars(select(Pass).where(Pass.status == "issued", Pass.valid_to < today)))


# ---------------------------------------------------------------- trips and positions


def running_trip(db: Session, route_id: str) -> Trip | None:
    q = _scoped(db, Trip).where(Trip.route_id == route_id, Trip.status == "running")
    return db.scalars(q.order_by(Trip.started_at.desc())).first()


def last_position(db: Session, trip_id: str) -> Position | None:
    q = _scoped(db, Position).where(Position.trip_id == trip_id)
    return db.scalars(q.order_by(Position.recorded_at.desc(), Position.id)).first()


def purge_positions(db: Session, before: datetime) -> int:
    """Across organisations: the caller runs this in platform scope (the daily job)."""
    result = db.execute(delete(Position).where(Position.recorded_at < before))
    return result.rowcount or 0


# ---------------------------------------------------------------- notices


def notices(db: Session, route_id: str | None = None) -> list[Notice]:
    q = _scoped(db, Notice)
    if route_id:
        q = q.where(Notice.route_id == route_id)
    return list(db.scalars(q.order_by(Notice.published_at.desc(), Notice.id)))


def candidate_notices_for(db: Session, route_ids: set[str]) -> list[Notice]:
    """Not withdrawn, for all routes or one of these, newest first. Expiry is checked by the caller."""
    target = Notice.route_id.is_(None)
    if route_ids:
        target = or_(target, Notice.route_id.in_(route_ids))
    q = _scoped(db, Notice).where(Notice.withdrawn_at.is_(None), target)
    return list(db.scalars(q.order_by(Notice.published_at.desc(), Notice.id)))
