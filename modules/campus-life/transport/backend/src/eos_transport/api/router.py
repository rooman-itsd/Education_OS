"""HTTP surface of transport, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/transport. Handlers only map HTTP to the use cases in application/service.py; each declares the
permission the contract names for it."""

from __future__ import annotations

from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, TransportError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["transport"])

LIMIT = Query(20, ge=1, le=100)


def _run(fn, *args):
    try:
        return fn(*args)
    except TransportError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- stops and routes


@router.get("/stops")
def list_stops(
    q: str | None = None, _: Actor = Depends(require(svc.ROUTE_READ, svc.SELF_READ)), db: Session = Depends(get_db)
):
    return svc.list_stops(db, q)


@router.post("/stops", status_code=201)
def create_stop(body: s.StopIn, a: Actor = Depends(require(svc.ROUTE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_stop, db, a, s.dump(body))


@router.patch("/stops/{stop_id}")
def update_stop(
    stop_id: str, body: s.StopIn, a: Actor = Depends(require(svc.ROUTE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_stop, db, a, stop_id, s.dump(body))


@router.get("/routes")
def list_routes(
    active: bool | None = None,
    stop_id: str | None = None,
    _: Actor = Depends(require(svc.ROUTE_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_routes(db, active, stop_id)


@router.post("/routes", status_code=201)
def create_route(body: s.RouteIn, a: Actor = Depends(require(svc.ROUTE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_route, db, a, s.dump(body))


@router.get("/routes/{route_id}")
def get_route(route_id: str, _: Actor = Depends(require(svc.ROUTE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_route, db, route_id)


@router.patch("/routes/{route_id}")
def update_route(
    route_id: str, body: s.RouteIn, a: Actor = Depends(require(svc.ROUTE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_route, db, a, route_id, s.dump(body))


@router.put("/routes/{route_id}/assignment")
def assign_route(
    route_id: str, body: s.AssignmentIn, a: Actor = Depends(require(svc.ROUTE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.assign_route, db, a, route_id, body.vehicle_id, body.driver_id)


@router.get("/routes/{route_id}/live")
def live(route_id: str, a: Actor = Depends(require(svc.TRACKING_READ, svc.SELF_READ)), db: Session = Depends(get_db)):
    return _run(svc.live, db, a, route_id)


# ---------------------------------------------------------------- vehicles and drivers


@router.get("/vehicles")
def list_vehicles(
    active: bool | None = None,
    expiring_within_days: int | None = Query(default=None, ge=0),
    _: Actor = Depends(require(svc.VEHICLE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_vehicles(db, active, expiring_within_days)


@router.post("/vehicles", status_code=201)
def create_vehicle(body: s.VehicleIn, a: Actor = Depends(require(svc.VEHICLE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_vehicle, db, a, s.dump(body))


@router.patch("/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: str, body: s.VehicleIn, a: Actor = Depends(require(svc.VEHICLE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_vehicle, db, a, vehicle_id, s.dump(body))


@router.get("/drivers")
def list_drivers(
    active: bool | None = None,
    expiring_within_days: int | None = Query(default=None, ge=0),
    _: Actor = Depends(require(svc.VEHICLE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_drivers(db, active, expiring_within_days)


@router.post("/drivers", status_code=201)
def create_driver(body: s.DriverIn, a: Actor = Depends(require(svc.VEHICLE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_driver, db, a, s.dump(body))


@router.patch("/drivers/{driver_id}")
def update_driver(
    driver_id: str, body: s.DriverIn, a: Actor = Depends(require(svc.VEHICLE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_driver, db, a, driver_id, s.dump(body))


# ---------------------------------------------------------------- passes


@router.get("/passes")
def list_passes(
    status: Literal["requested", "issued", "rejected", "cancelled", "expired"] | None = None,
    route_id: str | None = None,
    person_id: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.PASS_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_passes(db, {"status": status, "route_id": route_id, "person_id": person_id}, cursor, limit)


@router.post("/passes", status_code=201)
def issue_pass(body: s.PassIssueIn, a: Actor = Depends(require(svc.PASS_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.issue_pass, db, a, body.model_dump())


@router.post("/passes/{pass_id}/decision")
def decide_pass(
    pass_id: str, body: s.DecisionIn, a: Actor = Depends(require(svc.PASS_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.decide_pass, db, a, pass_id, body.model_dump())


@router.post("/passes/{pass_id}/cancel")
def cancel_pass(
    pass_id: str,
    body: s.ReasonIn,
    a: Actor = Depends(require(svc.PASS_MANAGE, svc.SELF_REQUEST)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_pass, db, a, pass_id, body.reason)


# ---------------------------------------------------------------- trips


@router.post("/trips", status_code=201)
def start_trip(body: s.TripIn, a: Actor = Depends(require(svc.TRACKING_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.start_trip, db, a, body.route_id)


@router.post("/trips/{trip_id}/positions", status_code=204)
def record_positions(
    trip_id: str,
    body: list[s.PositionIn] = Body(min_length=1, max_length=100),
    a: Actor = Depends(require(svc.TRACKING_RECORD)),
    db: Session = Depends(get_db),
):
    _run(svc.record_positions, db, a, trip_id, [p.model_dump() for p in body])
    return Response(status_code=204)


@router.put("/trips/{trip_id}/delay")
def report_delay(
    trip_id: str, body: s.DelayIn, a: Actor = Depends(require(svc.TRACKING_RECORD)), db: Session = Depends(get_db)
):
    return _run(svc.report_delay, db, a, trip_id, body.delay_minutes, body.note)


@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: str, a: Actor = Depends(require(svc.TRACKING_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.end_trip, db, a, trip_id)


# ---------------------------------------------------------------- notices


@router.get("/notices")
def list_notices(
    route_id: str | None = None, _: Actor = Depends(require(svc.NOTICE_PUBLISH)), db: Session = Depends(get_db)
):
    return svc.list_notices(db, route_id)


@router.post("/notices", status_code=201)
def publish_notice(
    body: s.NoticeIn,
    a: Actor = Depends(require(svc.NOTICE_PUBLISH, svc.TRACKING_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(svc.publish_notice, db, a, s.dump(body))


@router.post("/notices/{notice_id}/withdraw")
def withdraw_notice(notice_id: str, a: Actor = Depends(require(svc.NOTICE_PUBLISH)), db: Session = Depends(get_db)):
    return _run(svc.withdraw_notice, db, a, notice_id)


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/passes")
def my_passes(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_passes(db, a)


@router.post("/me/passes", status_code=201)
def request_pass(body: s.PassRequestIn, a: Actor = Depends(require(svc.SELF_REQUEST)), db: Session = Depends(get_db)):
    return _run(svc.request_pass, db, a, s.dump(body))


@router.get("/me/notices")
def my_notices(limit: int = LIMIT, a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_notices(db, a, limit)
