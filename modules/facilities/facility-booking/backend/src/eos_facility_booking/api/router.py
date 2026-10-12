"""HTTP surface of facility-booking, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/facility-booking. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, BookingError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["facility-booking"])

PAGE = Query(1, ge=1)
PAGE_SIZE = Query(50, ge=1, le=200)


def _fail(e: BookingError) -> HTTPException:
    return HTTPException(e.status, e.body())


def _run(fn, *args):
    try:
        return fn(*args)
    except BookingError as e:
        raise _fail(e) from e


# ---------------------------------------------------------------- resource types


@router.get("/resource-types")
def list_resource_types(_: Actor = Depends(require(svc.RESOURCE_READ)), db: Session = Depends(get_db)):
    return svc.list_resource_types(db)


@router.post("/resource-types", status_code=201)
def create_resource_type(
    body: s.ResourceTypeIn, a: Actor = Depends(require(svc.RESOURCE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_resource_type, db, a, s.dump(body))


@router.patch("/resource-types/{type_id}")
def update_resource_type(
    type_id: str,
    body: s.ResourceTypePatch,
    a: Actor = Depends(require(svc.RESOURCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_resource_type, db, a, type_id, s.dump(body, partial=True))


@router.delete("/resource-types/{type_id}", status_code=204)
def delete_resource_type(type_id: str, a: Actor = Depends(require(svc.RESOURCE_MANAGE)), db: Session = Depends(get_db)):
    _run(svc.delete_resource_type, db, a, type_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- resources


@router.get("/resources")
def list_resources(
    type_id: str | None = None,
    status: Literal["active", "inactive", "under_maintenance"] | None = None,
    min_capacity: int | None = Query(None, ge=1),
    q: str | None = None,
    free_from: datetime | None = None,
    free_to: datetime | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.RESOURCE_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "type_id": type_id,
        "status": status,
        "min_capacity": min_capacity,
        "q": q,
        "free_from": free_from,
        "free_to": free_to,
    }
    return svc.list_resources(db, a, filters, page, page_size)


@router.post("/resources", status_code=201)
def create_resource(
    body: s.ResourceIn, a: Actor = Depends(require(svc.RESOURCE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_resource, db, a, s.dump(body))


@router.get("/resources/{resource_id}")
def get_resource(resource_id: str, _: Actor = Depends(require(svc.RESOURCE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_resource, db, resource_id)


@router.patch("/resources/{resource_id}")
def update_resource(
    resource_id: str,
    body: s.ResourcePatch,
    a: Actor = Depends(require(svc.RESOURCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_resource, db, a, resource_id, s.dump(body, partial=True))


@router.put("/resources/{resource_id}/status")
def set_resource_status(
    resource_id: str, body: s.StatusIn, a: Actor = Depends(require(svc.RESOURCE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.set_resource_status, db, a, resource_id, body.status, body.reason)


@router.get("/resources/{resource_id}/availability")
def availability(
    resource_id: str,
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    a: Actor = Depends(require(svc.RESOURCE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.availability, db, a, resource_id, from_, to)


@router.put("/resources/{resource_id}/opening-hours")
def set_opening_hours(
    resource_id: str,
    body: list[s.OpeningHoursIn],
    a: Actor = Depends(require(svc.RESOURCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_opening_hours, db, a, resource_id, [h.model_dump() for h in body])


@router.get("/resources/{resource_id}/blackouts")
def list_blackouts(
    resource_id: str,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    _: Actor = Depends(require(svc.RESOURCE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_blackouts, db, resource_id, from_, to)


@router.post("/resources/{resource_id}/blackouts", status_code=201)
def add_blackout(
    resource_id: str,
    body: s.BlackoutIn,
    a: Actor = Depends(require(svc.RESOURCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_blackout, db, a, resource_id, s.dump(body))


@router.delete("/blackouts/{blackout_id}", status_code=204)
def delete_blackout(blackout_id: str, a: Actor = Depends(require(svc.RESOURCE_MANAGE)), db: Session = Depends(get_db)):
    _run(svc.delete_blackout, db, a, blackout_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- bookings


@router.get("/bookings")
def list_bookings(
    scope: Literal["mine", "managed"] = "mine",
    date: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: datetime | None = None,
    resource_id: str | None = None,
    type_id: str | None = None,
    status: str | None = Query(None, description="Comma-separated BookingStatus values"),
    source_module: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.BOOKING_READ)),
    db: Session = Depends(get_db),
):
    q = {
        "scope": scope,
        "date": date,
        "from": from_,
        "to": to,
        "resource_id": resource_id,
        "type_id": type_id,
        "status": [x for x in (status or "").split(",") if x],
        "source_module": source_module,
    }
    return _run(svc.list_bookings, db, a, q, page, page_size)


@router.post("/bookings", status_code=201)
def create_booking(body: s.BookingIn, a: Actor = Depends(require(svc.BOOKING_CREATE)), db: Session = Depends(get_db)):
    return _run(svc.create_booking, db, a, s.dump(body))


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, a: Actor = Depends(require(svc.BOOKING_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_booking, db, a, booking_id)


@router.patch("/bookings/{booking_id}")
def update_booking(
    booking_id: str,
    body: s.BookingPatch,
    a: Actor = Depends(require(svc.BOOKING_CREATE, svc.BOOKING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_booking, db, a, booking_id, s.dump(body, partial=True))


@router.post("/bookings/{booking_id}/approve")
def approve_booking(
    booking_id: str,
    body: s.NoteIn | None = None,
    a: Actor = Depends(require(svc.BOOKING_APPROVE, svc.BOOKING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_booking, db, a, booking_id, True, body.note if body else None)


@router.post("/bookings/{booking_id}/reject")
def reject_booking(
    booking_id: str,
    body: s.RequiredReasonIn,
    a: Actor = Depends(require(svc.BOOKING_APPROVE, svc.BOOKING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_booking, db, a, booking_id, False, body.reason)


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: str,
    body: s.ReasonIn | None = None,
    a: Actor = Depends(require(svc.BOOKING_CREATE, svc.BOOKING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_booking, db, a, booking_id, body.reason if body else None)


@router.post("/bookings/{booking_id}/check-in")
def check_in(
    booking_id: str, a: Actor = Depends(require(svc.BOOKING_CREATE, svc.BOOKING_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.check_in, db, a, booking_id)


@router.post("/bookings/{booking_id}/no-show")
def record_no_show(booking_id: str, a: Actor = Depends(require(svc.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.record_no_show, db, a, booking_id)


@router.post("/series/{series_id}/cancel")
def cancel_series(
    series_id: str,
    body: s.ReasonIn | None = None,
    a: Actor = Depends(require(svc.BOOKING_CREATE, svc.BOOKING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_series, db, a, series_id, body.reason if body else None)


@router.get("/summary")
def summary(date: str | None = None, a: Actor = Depends(require(svc.BOOKING_READ)), db: Session = Depends(get_db)):
    return _run(svc.summary, db, a, date)
