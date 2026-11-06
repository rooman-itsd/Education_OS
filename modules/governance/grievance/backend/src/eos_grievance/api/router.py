"""HTTP surface of grievance, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/grievance (apps/backend/config/modules.enabled.yaml, enabled in a later pull request). Handlers only map HTTP to
the use cases in application/service.py; each declares the permissions the contract names for it. Case operations are
also limited by committee membership, which the use cases check. Error bodies are {code, message} inside FastAPI's
`detail`."""

from __future__ import annotations

import re
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import GrievanceError
from ..domain.cases import COMMITTEE_KINDS, STATUSES, TRACKS
from . import schemas as s
from .deps import no_nul, require

router = APIRouter(tags=["grievance"], dependencies=[Depends(no_nul)])

LIMIT = Query(20, ge=1, le=100)
UUID = re.compile(s.UUID_PATTERN)

COMMITTEES_READ = require(perm.COMMITTEE_MANAGE, perm.CASE_READ, perm.CASE_FILE)
COMMITTEES_MANAGE = require(perm.COMMITTEE_MANAGE)
FILE = require(perm.CASE_FILE)
OWN = require(perm.CASE_READ_OWN)
READ = require(perm.CASE_READ)
MANAGE = require(perm.CASE_MANAGE)
APPEAL_DECIDE = require(perm.APPEAL_DECIDE)
STATS = require(perm.STATS_READ)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except GrievanceError as e:
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
        raise HTTPException(422, {"code": f"invalid_{field}", "message": f"{field} must be one uuid"})
    return value


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`status` is an array in form style without explode: status=submitted,acknowledged."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise HTTPException(422, {"code": f"invalid_{field}", "message": f"unknown {field} {', '.join(unknown)}"})
    return values


# ---------------------------------------------------------------- committees


@router.get("/committees")
def list_committees(
    kind: Literal[COMMITTEE_KINDS] | None = None,  # type: ignore[valid-type]
    active: bool | None = None,
    a: Actor = Depends(COMMITTEES_READ),
    db: Session = Depends(get_db),
):
    return _run(svc.list_committees, db, a, kind, active)


@router.post("/committees", status_code=201)
def create_committee(body: s.CommitteeInput, a: Actor = Depends(COMMITTEES_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_committee, db, a, s.as_dict(body, partial=False))


@router.patch("/committees/{committee_id}")
def update_committee(
    committee_id: str,
    body: s.CommitteeUpdateInput,
    a: Actor = Depends(COMMITTEES_MANAGE),
    db: Session = Depends(get_db),
):
    return _run(svc.update_committee, db, a, _path_id(committee_id, "committee"), s.as_dict(body, partial=True))


# ---------------------------------------------------------------- the caller's own cases


@router.post("/me/grievances", status_code=201)
def file_case(body: s.GrievanceInput, a: Actor = Depends(FILE), db: Session = Depends(get_db)):
    return _run(svc.file_case, db, a, s.as_dict(body, partial=False))


@router.get("/me/grievances")
def list_my_cases(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(OWN),
    db: Session = Depends(get_db),
):
    return _run(svc.list_my_cases, db, a, _listed(status, STATUSES, "status"), cursor, limit)


@router.get("/me/grievances/{case_id}")
def get_my_case(case_id: str, a: Actor = Depends(OWN), db: Session = Depends(get_db)):
    return _run(svc.get_my_case, db, a, _path_id(case_id, "case"))


@router.post("/me/grievances/{case_id}/updates", status_code=201)
def add_my_update(case_id: str, body: s.UpdateInput, a: Actor = Depends(OWN), db: Session = Depends(get_db)):
    return _run(svc.add_my_update, db, a, _path_id(case_id, "case"), body.body)


@router.post("/me/grievances/{case_id}/withdraw")
def withdraw_case(
    case_id: str,
    body: s.WithdrawInput | None = Body(default=None),
    a: Actor = Depends(OWN),
    db: Session = Depends(get_db),
):
    return _run(svc.withdraw_case, db, a, _path_id(case_id, "case"), body.reason if body else None)


@router.post("/me/grievances/{case_id}/appeal")
def appeal_case(case_id: str, body: s.AppealInput, a: Actor = Depends(OWN), db: Session = Depends(get_db)):
    return _run(svc.appeal_case, db, a, _path_id(case_id, "case"), body.reason)


# ---------------------------------------------------------------- committee side


@router.get("/grievances")
def list_cases(
    committee_id: str | None = None,
    track: Literal[TRACKS] | None = None,  # type: ignore[valid-type]
    status: str | None = None,
    overdue: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_cases,
        db,
        a,
        committee_id=_uuid_query(committee_id, "committee_id"),
        track=track,
        statuses=_listed(status, STATUSES, "status"),
        overdue=overdue,
        cursor=cursor,
        limit=limit,
    )


@router.get("/grievances/{case_id}")
def get_case(case_id: str, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_case, db, a, _path_id(case_id, "case"))


@router.post("/grievances/{case_id}/status")
def move_case(case_id: str, body: s.StatusInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.move_case, db, a, _path_id(case_id, "case"), body.status, body.reason)


@router.post("/grievances/{case_id}/updates", status_code=201)
def add_update(case_id: str, body: s.UpdateInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.add_update, db, a, _path_id(case_id, "case"), body.body)


@router.post("/grievances/{case_id}/proceedings", status_code=201)
def add_proceeding(case_id: str, body: s.ProceedingInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.add_proceeding, db, a, _path_id(case_id, "case"), s.as_dict(body, partial=False))


@router.post("/grievances/{case_id}/decision")
def decide_case(case_id: str, body: s.DecisionInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.decide_case, db, a, _path_id(case_id, "case"), s.as_dict(body, partial=False))


@router.post("/grievances/{case_id}/transfer")
def transfer_case(case_id: str, body: s.TransferInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.transfer_case, db, a, _path_id(case_id, "case"), s.as_dict(body, partial=False))


@router.post("/grievances/{case_id}/appeal-decision")
def decide_appeal(
    case_id: str, body: s.AppealDecisionInput, a: Actor = Depends(APPEAL_DECIDE), db: Session = Depends(get_db)
):
    return _run(svc.decide_appeal, db, a, _path_id(case_id, "case"), s.as_dict(body, partial=False))


# ---------------------------------------------------------------- counts (widgets)


@router.get("/stats/open-by-committee")
def open_by_committee(a: Actor = Depends(STATS), db: Session = Depends(get_db)):
    return _run(svc.open_by_committee, db, a)


@router.get("/stats/open")
def open_by_track(a: Actor = Depends(STATS), db: Session = Depends(get_db)):
    return _run(svc.open_by_track, db, a)
