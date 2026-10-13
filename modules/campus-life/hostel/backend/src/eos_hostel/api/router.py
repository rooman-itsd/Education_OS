"""HTTP surface of hostel, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/hostel. Handlers only map HTTP to the use cases in application/service.py; each declares the
permission the contract names for it."""

from __future__ import annotations

from datetime import date
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, HostelError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["hostel"])

LIMIT = Query(20, ge=1, le=100)


def _run(fn, *args):
    try:
        return fn(*args)
    except HostelError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- hostels and rooms


@router.get("/hostels")
def list_hostels(
    active: bool | None = None, _: Actor = Depends(require(svc.HOSTEL_READ)), db: Session = Depends(get_db)
):
    return svc.list_hostels(db, active)


@router.post("/hostels", status_code=201)
def create_hostel(body: s.HostelIn, a: Actor = Depends(require(svc.HOSTEL_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_hostel, db, a, s.dump(body))


@router.get("/hostels/{hostel_id}")
def get_hostel(hostel_id: str, _: Actor = Depends(require(svc.HOSTEL_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_hostel, db, hostel_id)


@router.patch("/hostels/{hostel_id}")
def update_hostel(
    hostel_id: str, body: s.HostelPatch, a: Actor = Depends(require(svc.HOSTEL_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_hostel, db, a, hostel_id, s.dump(body))


@router.get("/hostels/{hostel_id}/rooms")
def list_rooms(
    hostel_id: str,
    status: Literal["open", "closed"] | None = None,
    has_free_bed: bool | None = None,
    _: Actor = Depends(require(svc.HOSTEL_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_rooms, db, hostel_id, status, has_free_bed)


@router.post("/hostels/{hostel_id}/rooms", status_code=201)
def add_room(
    hostel_id: str, body: s.RoomIn, a: Actor = Depends(require(svc.HOSTEL_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.add_room, db, a, hostel_id, s.dump(body))


@router.patch("/rooms/{room_id}")
def update_room(
    room_id: str, body: s.RoomUpdate, a: Actor = Depends(require(svc.HOSTEL_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_room, db, a, room_id, s.dump(body))


# ---------------------------------------------------------------- allocations


@router.get("/allocations")
def list_allocations(
    status: Literal["requested", "confirmed", "occupied", "vacated", "cancelled"] | None = None,
    hostel_id: str | None = None,
    academic_year: str | None = None,
    person_id: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.ALLOCATION_READ)),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "hostel_id": hostel_id, "academic_year": academic_year, "person_id": person_id}
    return svc.list_allocations(db, filters, cursor, limit)


@router.post("/allocations", status_code=201)
def allocate(body: s.AllocationIn, a: Actor = Depends(require(svc.ALLOCATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.allocate_direct, db, a, s.dump(body))


@router.get("/allocations/{allocation_id}")
def get_allocation(allocation_id: str, _: Actor = Depends(require(svc.ALLOCATION_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_allocation, db, allocation_id)


@router.post("/allocations/{allocation_id}/confirm")
def confirm(
    allocation_id: str,
    body: s.ConfirmIn,
    a: Actor = Depends(require(svc.ALLOCATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.confirm_allocation, db, a, allocation_id, s.dump(body))


@router.post("/allocations/{allocation_id}/check-in")
def check_in(allocation_id: str, a: Actor = Depends(require(svc.ALLOCATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.check_in, db, a, allocation_id)


@router.post("/allocations/{allocation_id}/check-out")
def check_out(
    allocation_id: str,
    body: s.CheckOutIn | None = None,
    a: Actor = Depends(require(svc.ALLOCATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.check_out, db, a, allocation_id, body.condition_notes if body else None)


@router.post("/allocations/{allocation_id}/cancel")
def cancel(
    allocation_id: str,
    body: s.ReasonIn,
    a: Actor = Depends(require(svc.ALLOCATION_MANAGE, svc.SELF_REQUEST)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_allocation, db, a, allocation_id, body.reason)


# ---------------------------------------------------------------- mess menu


@router.get("/mess-menus")
def get_menus(
    hostel_id: str,
    from_: date = Query(alias="from"),
    to: date = Query(),
    _: Actor = Depends(require(svc.HOSTEL_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_menus, db, hostel_id, from_, to)


@router.put("/mess-menus")
def set_menus(body: list[s.MessMenuIn], a: Actor = Depends(require(svc.MESS_MANAGE)), db: Session = Depends(get_db)):
    entries = [{"hostel_id": m.hostel_id, "date": m.menu_date, "meal": m.meal, "items": m.items} for m in body]
    return _run(svc.set_menus, db, a, entries)


# ---------------------------------------------------------------- leave


@router.get("/leave-requests")
def list_leave(
    status: Literal["requested", "approved", "rejected", "withdrawn", "out", "returned"] | None = None,
    hostel_id: str | None = None,
    overdue: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.LEAVE_APPROVE, svc.GATE_RECORD)),
    db: Session = Depends(get_db),
):
    return svc.list_leave(db, status, hostel_id, overdue, cursor, limit)


@router.post("/leave-requests/{leave_id}/decision")
def decide_leave(
    leave_id: str, body: s.DecisionIn, a: Actor = Depends(require(svc.LEAVE_APPROVE)), db: Session = Depends(get_db)
):
    return _run(svc.decide_leave, db, a, leave_id, body.decision, body.reason)


@router.post("/leave-requests/{leave_id}/return")
def mark_returned(leave_id: str, a: Actor = Depends(require(svc.LEAVE_APPROVE)), db: Session = Depends(get_db)):
    return _run(svc.mark_returned, db, a, leave_id)


@router.post("/leave-requests/{leave_id}/gate-out")
def gate_out(leave_id: str, a: Actor = Depends(require(svc.GATE_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.gate_out, db, a, leave_id)


@router.post("/leave-requests/{leave_id}/gate-in")
def gate_in(leave_id: str, a: Actor = Depends(require(svc.GATE_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.gate_in, db, a, leave_id)


# ---------------------------------------------------------------- visits


@router.get("/visits")
def list_visits(
    hostel_id: str | None = None,
    person_id: str | None = None,
    on: date | None = Query(default=None, alias="date"),
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.VISITOR_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_visits(db, hostel_id, person_id, on, cursor, limit)


@router.post("/visits", status_code=201)
def record_visit(body: s.VisitIn, a: Actor = Depends(require(svc.VISITOR_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.record_visit, db, a, s.dump(body))


@router.post("/visits/{visit_id}/out")
def visit_out(visit_id: str, a: Actor = Depends(require(svc.VISITOR_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.visit_out, db, a, visit_id)


# ---------------------------------------------------------------- incidents


@router.get("/incidents")
def list_incidents(
    hostel_id: str | None = None,
    person_id: str | None = None,
    status: Literal["open", "closed"] | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.INCIDENT_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_incidents(db, hostel_id, person_id, status, cursor, limit)


@router.post("/incidents", status_code=201)
def record_incident(
    body: s.IncidentIn, a: Actor = Depends(require(svc.INCIDENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.record_incident, db, a, s.dump(body))


@router.patch("/incidents/{incident_id}")
def update_incident(
    incident_id: str,
    body: s.IncidentPatch,
    a: Actor = Depends(require(svc.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_incident, db, a, incident_id, s.dump(body))


# ---------------------------------------------------------------- notices


@router.get("/notices")
def list_notices(
    hostel_id: str | None = None, _: Actor = Depends(require(svc.NOTICE_PUBLISH)), db: Session = Depends(get_db)
):
    return svc.list_notices(db, hostel_id)


@router.post("/notices", status_code=201)
def publish_notice(body: s.NoticeIn, a: Actor = Depends(require(svc.NOTICE_PUBLISH)), db: Session = Depends(get_db)):
    return _run(svc.publish_notice, db, a, s.dump(body))


@router.post("/notices/{notice_id}/withdraw")
def withdraw_notice(notice_id: str, a: Actor = Depends(require(svc.NOTICE_PUBLISH)), db: Session = Depends(get_db)):
    return _run(svc.withdraw_notice, db, a, notice_id)


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/allocation")
def my_allocation(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_allocation(db, a)


@router.post("/me/room-requests", status_code=201)
def request_room(body: s.RoomRequestIn, a: Actor = Depends(require(svc.SELF_REQUEST)), db: Session = Depends(get_db)):
    return _run(svc.request_room, db, a, s.dump(body))


@router.get("/me/notices")
def my_notices(limit: int = LIMIT, a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_notices(db, a, limit)


@router.get("/me/leave-requests")
def my_leave(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_leave(db, a)


@router.post("/me/leave-requests", status_code=201)
def apply_leave(body: s.LeaveIn, a: Actor = Depends(require(svc.SELF_REQUEST)), db: Session = Depends(get_db)):
    return _run(svc.apply_leave, db, a, s.dump(body))


@router.post("/me/leave-requests/{leave_id}/withdraw")
def withdraw_leave(leave_id: str, a: Actor = Depends(require(svc.SELF_REQUEST)), db: Session = Depends(get_db)):
    return _run(svc.withdraw_leave, db, a, leave_id)


@router.get("/me/visits")
def my_visits(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_visits(db, a)
