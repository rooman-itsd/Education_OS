"""HTTP surface of sports-facilities, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/sports-facilities. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["sports-facilities"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- facilities


@router.get("/facilities")
def list_facilities(
    facility_type: s.FacilityType | None = None,
    sport: str | None = None,
    status: s.Status | None = None,
    indoor: bool | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.FACILITY_READ)),
    db: Session = Depends(get_db),
):
    filters = {"facility_type": facility_type, "sport": sport, "status": status, "indoor": indoor}
    return svc.list_facilities(db, filters, limit, offset)


@router.post("/facilities", status_code=201)
def create_facility(body: s.FacilityIn, a: Actor = Depends(require(svc.FACILITY_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_facility, db, a, s.dump(body))


@router.get("/facilities/{facility_id}")
def get_facility(facility_id: str, _: Actor = Depends(require(svc.FACILITY_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_facility, db, facility_id)


@router.patch("/facilities/{facility_id}")
def update_facility(
    facility_id: str,
    body: s.FacilityPatch,
    a: Actor = Depends(require(svc.FACILITY_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_facility, db, a, facility_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- spaces


@router.get("/facilities/{facility_id}/spaces")
def list_spaces(
    facility_id: str,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.FACILITY_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_spaces, db, facility_id, limit, offset)


@router.post("/facilities/{facility_id}/spaces", status_code=201)
def create_space(
    facility_id: str, body: s.SpaceIn, a: Actor = Depends(require(svc.FACILITY_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_space, db, a, facility_id, s.dump(body))


@router.patch("/facilities/{facility_id}/spaces/{space_id}")
def update_space(
    facility_id: str,
    space_id: str,
    body: s.SpacePatch,
    a: Actor = Depends(require(svc.FACILITY_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_space, db, a, facility_id, space_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- operating hours and status


@router.get("/facilities/{facility_id}/hours")
def get_operating_hours(
    facility_id: str, _: Actor = Depends(require(svc.FACILITY_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_hours, db, facility_id)


@router.put("/facilities/{facility_id}/hours")
def set_operating_hours(
    facility_id: str,
    body: s.OperatingHoursIn,
    a: Actor = Depends(require(svc.FACILITY_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_hours, db, a, facility_id, [slot.model_dump() for slot in body.slots])


@router.put("/facilities/{facility_id}/status")
def set_facility_status(
    facility_id: str,
    body: s.StatusIn,
    a: Actor = Depends(require(svc.FACILITY_STATUS)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_status, db, a, facility_id, s.dump(body))


@router.get("/facilities/{facility_id}/utilisation")
def get_utilisation(
    facility_id: str,
    from_: date = Query(alias="from"),
    to: date = Query(),
    _: Actor = Depends(require(svc.USAGE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.utilisation, db, facility_id, from_, to)


# ---------------------------------------------------------------- usage


@router.get("/usage")
def list_usages(
    facility_id: str | None = None,
    purpose: s.Purpose | None = None,
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.USAGE_READ)),
    db: Session = Depends(get_db),
):
    filters = {"facility_id": facility_id, "purpose": purpose, "from": from_, "to": to}
    return svc.list_usages(db, filters, limit, offset)


@router.post("/usage", status_code=201)
def record_usage(body: s.UsageIn, a: Actor = Depends(require(svc.USAGE_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.record_usage, db, a, s.dump(body))


@router.get("/usage/{usage_id}")
def get_usage(usage_id: str, _: Actor = Depends(require(svc.USAGE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_usage, db, usage_id)
