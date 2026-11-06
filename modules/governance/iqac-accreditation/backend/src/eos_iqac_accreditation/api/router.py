"""HTTP surface of iqac-accreditation, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/iqac-accreditation (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permissions the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`. Path parameters keep the contract's names (`id`, `evidence_id`)."""

from __future__ import annotations

import re
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import IqacAccreditationError
from ..infrastructure.models import CRITERION_LEN
from . import schemas as s
from .deps import StrictJsonRoute, no_nul, require

router = APIRouter(tags=["iqac-accreditation"], dependencies=[Depends(no_nul)], route_class=StrictJsonRoute)

LIMIT = Query(20, ge=1, le=100)
FRAMEWORKS_READ = require(*svc.FRAMEWORK_READERS)
FRAMEWORKS_MANAGE = require(perm.FRAMEWORK_MANAGE)
CYCLES_READ = require(perm.DATA_READ, perm.CYCLE_MANAGE)
CYCLES_MANAGE = require(perm.CYCLE_MANAGE)
RESPONSES_READ = require(perm.DATA_READ, perm.CYCLE_MANAGE, perm.RESPONSE_SUBMIT)
RESPONSES_SUBMIT = require(perm.RESPONSE_SUBMIT)
ACTION_ITEMS_READ = require(perm.DATA_READ, perm.ACTION_ITEM_MANAGE, perm.ACTION_ITEM_UPDATE_OWN)
ACTION_ITEMS_MANAGE = require(perm.ACTION_ITEM_MANAGE)
ACTION_ITEMS_UPDATE = require(perm.ACTION_ITEM_MANAGE, perm.ACTION_ITEM_UPDATE_OWN)
STATS = require(perm.STATS_READ)
UUID = re.compile(s.UUID_PATTERN)

CycleStatus = Literal["planning", "collecting", "under_review", "submitted", "closed"]
ResponseStatus = Literal["pending", "submitted", "returned", "accepted"]
ActionStatus = Literal["open", "in_progress", "done", "cancelled"]


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IqacAccreditationError as e:
        raise HTTPException(e.status, e.body()) from e


def _path_id(value: str, what: str) -> str:
    """A path id that is not a uuid names no row: 404, without a query."""
    if not UUID.match(value):
        raise HTTPException(404, {"code": "not_found", "message": f"{what} not found"})
    return value


def _uuid_query(value: str | None, field: str) -> str | None:
    """A query parameter the contract types as format: uuid, as one value: 422 otherwise (also for a comma list)."""
    if value is None:
        return None
    if not UUID.match(value):
        raise HTTPException(422, {"code": f"invalid_{field}", "message": f"{field} must be one uuid", "field": field})
    return value


def _owner(value: str | None) -> str | None:
    """owner is one person id or `me`."""
    if value is None or value == "me":
        return value
    return _uuid_query(value, "owner")


# ---------------------------------------------------------------- frameworks and metrics


@router.get("/frameworks")
def list_frameworks(active: bool | None = None, a: Actor = Depends(FRAMEWORKS_READ), db: Session = Depends(get_db)):
    return _run(svc.list_frameworks, db, a, active=active)


@router.post("/frameworks", status_code=201)
def create_framework(body: s.FrameworkInput, a: Actor = Depends(FRAMEWORKS_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_framework, db, a, s.as_dict(body, partial=False))


@router.patch("/frameworks/{id}")
def update_framework(
    id: str, body: s.FrameworkUpdateInput, a: Actor = Depends(FRAMEWORKS_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_framework, db, a, _path_id(id, "framework"), s.as_dict(body, partial=True))


@router.get("/frameworks/{id}/metrics")
def list_metrics(
    id: str,
    criterion: str | None = Query(None, max_length=CRITERION_LEN),
    active: bool | None = None,
    a: Actor = Depends(FRAMEWORKS_READ),
    db: Session = Depends(get_db),
):
    return _run(svc.list_metrics, db, a, _path_id(id, "framework"), criterion=criterion, active=active)


@router.post("/frameworks/{id}/metrics", status_code=201)
def create_metric(id: str, body: s.MetricInput, a: Actor = Depends(FRAMEWORKS_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_metric, db, a, _path_id(id, "framework"), s.as_dict(body, partial=False))


@router.patch("/metrics/{id}")
def update_metric(
    id: str, body: s.MetricUpdateInput, a: Actor = Depends(FRAMEWORKS_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_metric, db, a, _path_id(id, "metric"), s.as_dict(body, partial=True))


# ---------------------------------------------------------------- cycles


@router.get("/cycles")
def list_cycles(
    framework_id: str | None = None,
    status: CycleStatus | None = None,
    a: Actor = Depends(CYCLES_READ),
    db: Session = Depends(get_db),
):
    return _run(svc.list_cycles, db, a, framework_id=_uuid_query(framework_id, "framework_id"), status=status)


@router.post("/cycles", status_code=201)
def create_cycle(body: s.CycleInput, a: Actor = Depends(CYCLES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_cycle, db, a, s.as_dict(body, partial=False))


@router.get("/cycles/{id}")
def get_cycle(id: str, a: Actor = Depends(CYCLES_READ), db: Session = Depends(get_db)):
    return _run(svc.get_cycle, db, a, _path_id(id, "cycle"))


@router.patch("/cycles/{id}")
def update_cycle(id: str, body: s.CycleUpdateInput, a: Actor = Depends(CYCLES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.update_cycle, db, a, _path_id(id, "cycle"), s.as_dict(body, partial=True))


@router.post("/cycles/{id}/status")
def move_cycle(id: str, body: s.CycleStatusInput, a: Actor = Depends(CYCLES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.move_cycle, db, a, _path_id(id, "cycle"), s.as_dict(body, partial=False))


@router.post("/cycles/{id}/assignments", status_code=201)
def assign_metrics(id: str, body: s.AssignmentInput, a: Actor = Depends(CYCLES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.assign_metrics, db, a, _path_id(id, "cycle"), s.as_dict(body, partial=False))


# ---------------------------------------------------------------- responses


@router.get("/responses")
def list_responses(
    cycle_id: str | None = None,
    owner: str | None = None,
    status: ResponseStatus | None = None,
    overdue: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(RESPONSES_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_responses,
        db,
        a,
        cycle_id=_uuid_query(cycle_id, "cycle_id"),
        owner=_owner(owner),
        status=status,
        overdue=overdue,
        cursor=cursor,
        limit=limit,
    )


@router.get("/responses/{id}")
def get_response(id: str, a: Actor = Depends(RESPONSES_READ), db: Session = Depends(get_db)):
    return _run(svc.get_response, db, a, _path_id(id, "response"))


@router.put("/responses/{id}")
def save_response(id: str, body: s.ResponseInput, a: Actor = Depends(RESPONSES_SUBMIT), db: Session = Depends(get_db)):
    data = s.as_dict(body, partial=True, nullable=frozenset({"value", "narrative"}))
    return _run(svc.save_response, db, a, _path_id(id, "response"), data)


@router.post("/responses/{id}/submit")
def submit_response(id: str, a: Actor = Depends(RESPONSES_SUBMIT), db: Session = Depends(get_db)):
    return _run(svc.submit_response, db, a, _path_id(id, "response"))


@router.post("/responses/{id}/review")
def review_response(id: str, body: s.ReviewInput, a: Actor = Depends(CYCLES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.review_response, db, a, _path_id(id, "response"), s.as_dict(body, partial=False))


@router.post("/responses/{id}/evidence", status_code=201)
def add_evidence(id: str, body: s.EvidenceInput, a: Actor = Depends(RESPONSES_SUBMIT), db: Session = Depends(get_db)):
    return _run(svc.add_evidence, db, a, _path_id(id, "response"), s.as_dict(body, partial=False))


@router.delete("/responses/{id}/evidence/{evidence_id}", status_code=204)
def remove_evidence(id: str, evidence_id: str, a: Actor = Depends(RESPONSES_SUBMIT), db: Session = Depends(get_db)):
    _run(svc.remove_evidence, db, a, _path_id(id, "response"), _path_id(evidence_id, "evidence"))
    return Response(status_code=204)


# ---------------------------------------------------------------- action items and the widget


@router.get("/action-items")
def list_action_items(
    status: ActionStatus | None = None,
    owner: str | None = None,
    cycle_id: str | None = None,
    overdue: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(ACTION_ITEMS_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_action_items,
        db,
        a,
        status=status,
        owner=_owner(owner),
        cycle_id=_uuid_query(cycle_id, "cycle_id"),
        overdue=overdue,
        cursor=cursor,
        limit=limit,
    )


@router.post("/action-items", status_code=201)
def create_action_item(body: s.ActionItemInput, a: Actor = Depends(ACTION_ITEMS_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_action_item, db, a, s.as_dict(body, partial=False))


@router.patch("/action-items/{id}")
def update_action_item(
    id: str, body: s.ActionItemUpdateInput, a: Actor = Depends(ACTION_ITEMS_UPDATE), db: Session = Depends(get_db)
):
    return _run(svc.update_action_item, db, a, _path_id(id, "action item"), s.as_dict(body, partial=True))


@router.get("/stats/action-items")
def action_item_stats(a: Actor = Depends(STATS), db: Session = Depends(get_db)):
    return _run(svc.action_item_stats, db, a)
