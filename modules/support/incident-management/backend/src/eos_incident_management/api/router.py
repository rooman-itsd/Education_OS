"""HTTP surface of incident-management, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/incident-management (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permission the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

import re

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import IncidentManagementError
from ..domain.incidents import INCIDENT_STATUSES, SEVERITIES
from ..domain.problems import ACTION_STATUSES, PROBLEM_STATUSES
from . import schemas as s
from .deps import no_nul, require

router = APIRouter(tags=["incident-management"], dependencies=[Depends(no_nul)])

LIMIT = Query(20, ge=1, le=100)
SERVICE = Query(None, max_length=80)  # one affected service label (contract ServiceLabels items: maxLength 80)
SEARCH = Query(None, max_length=200)  # incident or problem number or title (String(200))
CURSOR = Query(None, max_length=100)
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

INCIDENT_READ = require(perm.INCIDENT_READ)
INCIDENT_REPORT = require(perm.INCIDENT_REPORT)
INCIDENT_MANAGE = require(perm.INCIDENT_MANAGE)
PROBLEM_READ = require(perm.PROBLEM_READ)
PROBLEM_MANAGE = require(perm.PROBLEM_MANAGE)
# PATCH /problems/{id}/actions/{action_id}: problem:manage, or problem:read for the owner marking it done; the use
# case tells the two apart.
ACTION_CHANGE = require(perm.PROBLEM_MANAGE, perm.PROBLEM_READ)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IncidentManagementError as e:
        raise HTTPException(e.status, e.body()) from e


def _refuse(field: str, message: str) -> HTTPException:
    return HTTPException(422, {"code": f"invalid_{field}", "message": message, "field": field})


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`status` is an array in form style without explode: status=open,investigating."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise _refuse(field, f"unknown {field} {', '.join(unknown)}")
    return values


def _single(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    """One enum value, not a list: severity=high,low is a 422, never a partial result."""
    if not value:
        return None
    if value not in allowed:
        raise _refuse(field, f"unknown {field} {value}")
    return value


def _person(value: str | None, field: str) -> str | None:
    """`lead` and `owner`: "me" or one person id (format uuid)."""
    if not value:
        return None
    if value == "me":
        return value
    if not UUID.fullmatch(value):
        raise _refuse(field, f"{field} must be me or a person id")
    return value.lower()


def _uuid(value: str | None, field: str) -> str | None:
    if not value:
        return None
    if not UUID.fullmatch(value):
        raise _refuse(field, f"{field} must be an id")
    return value.lower()


# ---------------------------------------------------------------- incidents


@router.get("/incidents")
def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    lead: str | None = None,
    problem_id: str | None = None,
    service: str | None = SERVICE,
    q: str | None = SEARCH,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(INCIDENT_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_incidents,
        db,
        a,
        statuses=_listed(status, INCIDENT_STATUSES, "status"),
        severity=_single(severity, SEVERITIES, "severity"),
        lead=_person(lead, "lead"),
        problem_id=_uuid(problem_id, "problem_id"),
        service=service,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.post("/incidents", status_code=201)
def report_incident(body: s.IncidentInput, a: Actor = Depends(INCIDENT_REPORT), db: Session = Depends(get_db)):
    return _run(svc.report_incident, db, a, s.as_dict(body, partial=False))


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, a: Actor = Depends(INCIDENT_READ), db: Session = Depends(get_db)):
    return _run(svc.get_incident, db, a, incident_id)


@router.patch("/incidents/{incident_id}")
def update_incident(
    incident_id: str, body: s.IncidentUpdateInput, a: Actor = Depends(INCIDENT_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_incident, db, a, incident_id, s.as_dict(body, partial=True))


@router.post("/incidents/{incident_id}/status")
def move_incident(
    incident_id: str, body: s.IncidentStatusInput, a: Actor = Depends(INCIDENT_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.move_incident, db, a, incident_id, s.as_dict(body, partial=False))


@router.post("/incidents/{incident_id}/updates", status_code=201)
def add_update(
    incident_id: str, body: s.TimelineInput, a: Actor = Depends(INCIDENT_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.add_update, db, a, incident_id, s.as_dict(body, partial=False))


@router.post("/incidents/{incident_id}/references", status_code=201)
def add_reference(
    incident_id: str, body: s.ReferenceInput, a: Actor = Depends(INCIDENT_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.add_reference, db, a, incident_id, s.as_dict(body, partial=False))


@router.delete("/incidents/{incident_id}/references/{reference_id}", status_code=204)
def remove_reference(
    incident_id: str, reference_id: str, a: Actor = Depends(INCIDENT_MANAGE), db: Session = Depends(get_db)
):
    _run(svc.remove_reference, db, a, incident_id, reference_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- problems


@router.get("/problems")
def list_problems(
    status: str | None = None,
    owner: str | None = None,
    service: str | None = SERVICE,
    q: str | None = SEARCH,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(PROBLEM_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_problems,
        db,
        a,
        statuses=_listed(status, PROBLEM_STATUSES, "status"),
        owner=_person(owner, "owner"),
        service=service,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.post("/problems", status_code=201)
def open_problem(body: s.ProblemInput, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.open_problem, db, a, s.as_dict(body, partial=False))


@router.get("/problems/{problem_id}")
def get_problem(problem_id: str, a: Actor = Depends(PROBLEM_READ), db: Session = Depends(get_db)):
    return _run(svc.get_problem, db, a, problem_id)


@router.patch("/problems/{problem_id}")
def update_problem(
    problem_id: str, body: s.ProblemUpdateInput, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_problem, db, a, problem_id, s.as_dict(body, partial=True))


@router.post("/problems/{problem_id}/status")
def move_problem(
    problem_id: str, body: s.ProblemStatusInput, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.move_problem, db, a, problem_id, s.as_dict(body, partial=False))


@router.get("/problems/{problem_id}/rca")
def get_rca(problem_id: str, a: Actor = Depends(PROBLEM_READ), db: Session = Depends(get_db)):
    return _run(svc.get_rca, db, a, problem_id)


@router.put("/problems/{problem_id}/rca")
def save_rca(problem_id: str, body: s.RcaInput, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.save_rca, db, a, problem_id, s.as_dict(body, partial=False))


@router.post("/problems/{problem_id}/rca/publish")
def publish_rca(problem_id: str, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.publish_rca, db, a, problem_id)


@router.post("/problems/{problem_id}/actions", status_code=201)
def add_action(problem_id: str, body: s.ActionInput, a: Actor = Depends(PROBLEM_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.add_action, db, a, problem_id, s.as_dict(body, partial=False))


@router.patch("/problems/{problem_id}/actions/{action_id}")
def update_action(
    problem_id: str,
    action_id: str,
    body: s.ActionUpdateInput,
    a: Actor = Depends(ACTION_CHANGE),
    db: Session = Depends(get_db),
):
    return _run(svc.update_action, db, a, problem_id, action_id, s.as_dict(body, partial=True))


# ---------------------------------------------------------------- actions and statistics


@router.get("/actions")
def list_actions(
    owner: str | None = None,
    status: str | None = None,
    overdue: bool | None = None,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(PROBLEM_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_actions,
        db,
        a,
        owner=_person(owner, "owner"),
        status=_single(status, ACTION_STATUSES, "status"),
        overdue=overdue,
        cursor=cursor,
        limit=limit,
    )


@router.get("/stats/open")
def open_stats(a: Actor = Depends(INCIDENT_READ), db: Session = Depends(get_db)):
    return _run(svc.open_stats, db, a)
