"""HTTP surface of maintenance, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/maintenance. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, MaintenanceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["maintenance"])

PAGE = Query(1, ge=1)
PAGE_SIZE = Query(50, ge=1, le=200)
PRIORITIES = {"low", "medium", "high", "urgent"}
STATUSES = {"open", "assigned", "in_progress", "on_hold", "resolved", "closed", "cancelled"}


def _run(fn, *args):
    try:
        return fn(*args)
    except MaintenanceError as e:
        raise HTTPException(e.status, e.body()) from e


def _csv(value: str | None, allowed: set[str], name: str) -> list[str] | None:
    """status and priority are comma-separated lists (style: form, explode: false)."""
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in items if v not in allowed]
    if bad:
        raise HTTPException(422, {"code": "invalid_query", "message": f"unknown {name}: {', '.join(bad)}"})
    return items


# ---------------------------------------------------------------- categories


@router.get("/categories")
def list_categories(_: Actor = Depends(require(svc.TICKET_CREATE)), db: Session = Depends(get_db)):
    return svc.list_categories(db)


@router.post("/categories", status_code=201)
def create_category(body: s.CategoryIn, a: Actor = Depends(require(svc.TICKET_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_category, db, a, s.dump(body))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str,
    body: s.CategoryPatch,
    a: Actor = Depends(require(svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_category, db, a, category_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- tickets


@router.get("/tickets")
def list_tickets(
    scope: Literal["mine", "assigned", "managed"] = "mine",
    status: str | None = Query(None, description="Comma-separated TicketStatus values"),
    open: bool | None = None,
    priority: str | None = Query(None, description="Comma-separated Priority values"),
    kind: Literal["corrective", "preventive", "inspection"] | None = None,
    category_id: str | None = None,
    target_kind: Literal["asset", "resource", "unit", "location"] | None = None,
    target_id: str | None = None,
    assignee_id: str | None = None,
    sla_breached: bool | None = None,
    q: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.TICKET_READ)),
    db: Session = Depends(get_db),
):
    query = {
        "scope": scope,
        "status": _csv(status, STATUSES, "status"),
        "open": open,
        "priority": _csv(priority, PRIORITIES, "priority"),
        "kind": kind,
        "category_id": category_id,
        "target_kind": target_kind,
        "target_id": target_id,
        "assignee_id": assignee_id,
        "sla_breached": sla_breached,
        "q": q,
    }
    return _run(svc.list_tickets, db, a, query, page, page_size)


@router.post("/tickets", status_code=201)
def raise_ticket(body: s.TicketIn, a: Actor = Depends(require(svc.TICKET_CREATE)), db: Session = Depends(get_db)):
    return _run(svc.raise_ticket, db, a, s.dump(body))


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, a: Actor = Depends(require(svc.TICKET_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_ticket, db, a, ticket_id)


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str, body: s.TicketPatch, a: Actor = Depends(require(svc.TICKET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_ticket, db, a, ticket_id, s.dump(body, partial=True))


@router.post("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str, body: s.AssignmentIn, a: Actor = Depends(require(svc.TICKET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.assign_ticket, db, a, ticket_id, s.dump(body))


@router.post("/tickets/{ticket_id}/start")
def start_ticket(
    ticket_id: str, a: Actor = Depends(require(svc.TICKET_WORK, svc.TICKET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.start_ticket, db, a, ticket_id)


@router.post("/tickets/{ticket_id}/hold")
def hold_ticket(
    ticket_id: str,
    body: s.HoldIn,
    a: Actor = Depends(require(svc.TICKET_WORK, svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.hold_ticket, db, a, ticket_id, body.reason, body.note)


@router.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: str,
    body: s.ResolutionIn,
    a: Actor = Depends(require(svc.TICKET_WORK, svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.resolve_ticket, db, a, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    body: s.CloseIn | None = Body(default=None),
    a: Actor = Depends(require(svc.TICKET_CREATE, svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.close_ticket, db, a, ticket_id, s.dump(body))


@router.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(
    ticket_id: str,
    body: s.ReopenIn,
    a: Actor = Depends(require(svc.TICKET_CREATE, svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.reopen_ticket, db, a, ticket_id, body.reason)


@router.post("/tickets/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: str,
    body: s.CancelIn,
    a: Actor = Depends(require(svc.TICKET_CREATE, svc.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_ticket, db, a, ticket_id, body.reason, body.duplicate_of)


@router.get("/tickets/{ticket_id}/work-entries")
def list_work_entries(ticket_id: str, a: Actor = Depends(require(svc.TICKET_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_entries, db, a, ticket_id)


@router.post("/tickets/{ticket_id}/work-entries", status_code=201)
def add_work_entry(
    ticket_id: str,
    body: s.WorkEntryIn,
    a: Actor = Depends(require(svc.TICKET_CREATE, svc.TICKET_WORK)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_entry, db, a, ticket_id, s.dump(body))


# ---------------------------------------------------------------- preventive schedules


@router.get("/schedules")
def list_schedules(
    active: bool | None = None,
    target_kind: Literal["asset", "resource", "unit", "location"] | None = None,
    target_id: str | None = None,
    due_before: date | None = None,
    _: Actor = Depends(require(svc.SCHEDULE_MANAGE)),
    db: Session = Depends(get_db),
):
    query = {"active": active, "target_kind": target_kind, "target_id": target_id, "due_before": due_before}
    return svc.list_schedules(db, query)


@router.post("/schedules", status_code=201)
def create_schedule(
    body: s.ScheduleIn, a: Actor = Depends(require(svc.SCHEDULE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_schedule, db, a, s.dump(body))


@router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: str, _: Actor = Depends(require(svc.SCHEDULE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.get_schedule, db, schedule_id)


@router.patch("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: str,
    body: s.SchedulePatch,
    a: Actor = Depends(require(svc.SCHEDULE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_schedule, db, a, schedule_id, s.dump(body, partial=True))


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, a: Actor = Depends(require(svc.SCHEDULE_MANAGE)), db: Session = Depends(get_db)):
    _run(svc.delete_schedule, db, a, schedule_id)
    return Response(status_code=204)


@router.post("/schedules/{schedule_id}/raise-now", status_code=201)
def raise_now(schedule_id: str, a: Actor = Depends(require(svc.SCHEDULE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.raise_now, db, a, schedule_id)


# ---------------------------------------------------------------- widget summary


@router.get("/summary")
def summary(a: Actor = Depends(require(svc.TICKET_READ)), db: Session = Depends(get_db)):
    return svc.summary(db, a)
