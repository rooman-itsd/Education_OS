"""HTTP surface of productions, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/productions. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ProductionsError
from ..domain.rules import STATUSES
from . import schemas as s
from .deps import require

router = APIRouter(tags=["productions"])

PAGE = Query(1, ge=1)
PAGE_SIZE = Query(50, ge=1, le=200)
LIMIT = Query(10, ge=1, le=100)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ProductionsError as e:
        raise HTTPException(e.status, e.body()) from e


def _statuses(raw: str | None) -> list[str] | None:
    """`?status=planned,in_preparation`. An unknown name is refused rather than silently matching nothing."""
    if not raw:
        return None
    wanted = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = [w for w in wanted if w not in STATUSES]
    if unknown:
        raise HTTPException(422, {"code": "invalid_status", "message": f"unknown status: {', '.join(sorted(unknown))}"})
    return wanted


# ---------------------------------------------------------------- productions


@router.get("/productions")
def list_productions(
    status: str | None = None,
    kind: str | None = None,
    department: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    q: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    _: Actor = Depends(require(svc.PRODUCTION_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "status": _statuses(status),
        "kind": kind,
        "department": department,
        "from": from_,
        "to": to,
        "q": q,
    }
    return svc.list_productions(db, filters, page, page_size)


@router.post("/productions")
def create_production(
    body: s.ProductionIn,
    response: Response,
    a: Actor = Depends(require(svc.PRODUCTION_MANAGE)),
    db: Session = Depends(get_db),
):
    production, created = _run(svc.create_production, db, a, s.dump(body))
    response.status_code = 201 if created else 200
    return production


@router.get("/productions/{production_id}")
def get_production(production_id: str, _: Actor = Depends(require(svc.PRODUCTION_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_production, db, production_id)


@router.patch("/productions/{production_id}")
def update_production(
    production_id: str,
    body: s.ProductionPatch,
    a: Actor = Depends(require(svc.PRODUCTION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_production, db, a, production_id, s.dump(body, partial=True))


@router.post("/productions/{production_id}/preparation")
def start_preparation(
    production_id: str, a: Actor = Depends(require(svc.PRODUCTION_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.start_preparation, db, a, production_id)


@router.post("/productions/{production_id}/schedule")
def schedule(
    production_id: str,
    body: s.ScheduleIn,
    a: Actor = Depends(require(svc.PRODUCTION_MANAGE)),
    db: Session = Depends(get_db),
):
    production, warnings = _run(svc.schedule, db, a, production_id, s.dump(body))
    return {**production, "warnings": warnings}


@router.post("/productions/{production_id}/complete")
def complete(production_id: str, a: Actor = Depends(require(svc.PRODUCTION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.complete, db, a, production_id)


@router.post("/productions/{production_id}/cancel")
def cancel(
    production_id: str,
    body: s.ReasonIn,
    a: Actor = Depends(require(svc.PRODUCTION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel, db, a, production_id, s.dump(body))


# ---------------------------------------------------------------- cast and crew


@router.get("/productions/{production_id}/roles")
def list_roles(production_id: str, _: Actor = Depends(require(svc.PRODUCTION_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_roles, db, production_id)


@router.post("/productions/{production_id}/roles")
def assign_role(
    production_id: str,
    body: s.RoleIn,
    response: Response,
    a: Actor = Depends(require(svc.ROLE_MANAGE)),
    db: Session = Depends(get_db),
):
    role, created = _run(svc.assign_role, db, a, production_id, s.dump(body))
    response.status_code = 201 if created else 200
    return role


@router.post("/roles/{role_id}/respond")
def respond(
    role_id: str,
    body: s.RespondIn,
    a: Actor = Depends(require(svc.ROLE_RESPOND)),
    db: Session = Depends(get_db),
):
    return _run(svc.respond, db, a, role_id, s.dump(body))


@router.delete("/roles/{role_id}")
def withdraw_role(
    role_id: str,
    body: s.ReasonIn | None = None,
    a: Actor = Depends(require(svc.ROLE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.withdraw_role, db, a, role_id, s.dump(body))


# ---------------------------------------------------------------- preparation tasks


@router.get("/productions/{production_id}/tasks")
def list_tasks(production_id: str, _: Actor = Depends(require(svc.TASK_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_tasks, db, production_id)


@router.post("/productions/{production_id}/tasks", status_code=201)
def add_task(
    production_id: str,
    body: s.TaskIn,
    a: Actor = Depends(require(svc.TASK_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_task, db, a, production_id, s.dump(body))


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, a: Actor = Depends(require(svc.TASK_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.complete_task, db, a, task_id)


# ---------------------------------------------------------------- dashboard widgets


@router.get("/calendar")
def calendar(
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.PRODUCTION_READ)),
    db: Session = Depends(get_db),
):
    return svc.calendar(db, from_, to, limit)


@router.get("/upcoming")
def upcoming(limit: int = LIMIT, _: Actor = Depends(require(svc.PRODUCTION_READ)), db: Session = Depends(get_db)):
    return svc.upcoming(db, limit)


@router.get("/my-roles")
def my_roles(
    open: bool = False,  # noqa: A002 - the query parameter is named `open` in the contract
    limit: int = LIMIT,
    a: Actor = Depends(require(svc.ROLE_READ_OWN)),
    db: Session = Depends(get_db),
):
    return svc.my_roles(db, a, open_only=open, limit=limit)


@router.get("/in-preparation")
def in_preparation(
    mine: bool = False,
    limit: int = LIMIT,
    a: Actor = Depends(require(svc.TASK_READ)),
    db: Session = Depends(get_db),
):
    return svc.in_preparation(db, a, mine=mine, limit=limit)
