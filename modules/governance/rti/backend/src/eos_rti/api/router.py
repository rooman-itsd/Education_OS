"""HTTP surface of rti, as described in contracts/openapi.yaml. The host app mounts `router` under /api/v1/rti
(apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in application/service.py; each
declares the permissions the contract names for it. Error bodies are {code, message[, field]} inside FastAPI's
`detail`."""

from __future__ import annotations

import re
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import RtiError
from ..domain.requests import CHANNELS, REQUEST_STATUSES
from . import schemas as s
from .deps import JsonRoute, no_nul, require

router = APIRouter(tags=["rti"], dependencies=[Depends(no_nul)], route_class=JsonRoute)

LIMIT = Query(20, ge=1, le=100)
READ = require(perm.REQUEST_READ)
MANAGE = require(perm.REQUEST_MANAGE)
REFERRALS = require(perm.REFERRAL_RESPOND, perm.REQUEST_READ)
RESPOND_TO_REFERRAL = require(perm.REFERRAL_RESPOND)
APPEALS = require(perm.APPEAL_DECIDE)
STATS = require(perm.STATS_READ)
UUID = re.compile(s.UUID_PATTERN)
Q_LEN = 200


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RtiError as e:
        raise HTTPException(e.status, e.body()) from e


def _path_id(value: str, what: str) -> str:
    """A path id that is not a uuid names no row: 404, without a query."""
    if not UUID.match(value):
        raise HTTPException(404, {"code": "not_found", "message": f"{what} not found"})
    return value.lower()


def _uuid_query(value: str | None, field: str) -> str | None:
    """A query parameter the contract types as format: uuid, as one value: 422 otherwise (also for a comma list)."""
    if value is None:
        return None
    if not UUID.match(value):
        raise HTTPException(422, {"code": f"invalid_{field}", "message": f"{field} must be one uuid", "field": field})
    return value.lower()


def _officer(value: str | None) -> str | None:
    """officer is one person id or `me`."""
    return value if value == "me" else _uuid_query(value, "officer")


def _statuses(value: str | None) -> list[str] | None:
    """`status` is an array in form style without explode: status=received,assigned."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in REQUEST_STATUSES]
    if unknown:
        raise HTTPException(
            422, {"code": "invalid_status", "message": f"unknown status {', '.join(unknown)}", "field": "status"}
        )
    return values


# ---------------------------------------------------------------- requests


@router.get("/requests")
def list_requests(
    status: str | None = Query(None, max_length=200),
    officer: str | None = Query(None, max_length=64),
    overdue: bool | None = None,
    received_via: Literal[CHANNELS] | None = None,  # type: ignore[valid-type]
    q: str | None = Query(None, max_length=Q_LEN),
    cursor: str | None = Query(None, max_length=16),
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_requests,
        db,
        a,
        statuses=_statuses(status),
        officer=_officer(officer),
        overdue=overdue,
        received_via=received_via,
        q=(q or "").strip() or None,
        cursor=cursor,
        limit=limit,
    )


@router.post("/requests", status_code=201)
def create_request(body: s.RequestInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_request, db, a, s.as_dict(body))


@router.get("/requests/{request_id}")
def get_request(request_id: str, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_request, db, a, _path_id(request_id, "request"))


@router.patch("/requests/{request_id}")
def update_request(
    request_id: str, body: s.RequestUpdateInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_request, db, a, _path_id(request_id, "request"), s.as_dict(body, partial=True))


@router.post("/requests/{request_id}/assign")
def assign_request(request_id: str, body: s.AssignInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.assign_request, db, a, _path_id(request_id, "request"), body.officer_id)


@router.post("/requests/{request_id}/referrals", status_code=201)
def create_referral(request_id: str, body: s.ReferralInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_referral, db, a, _path_id(request_id, "request"), s.as_dict(body, partial=True))


@router.post("/requests/{request_id}/respond")
def respond(request_id: str, body: s.ResponseInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.respond, db, a, _path_id(request_id, "request"), s.as_dict(body, partial=True))


@router.post("/requests/{request_id}/transfer")
def transfer(request_id: str, body: s.TransferInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.transfer, db, a, _path_id(request_id, "request"), s.as_dict(body, partial=True))


@router.post("/requests/{request_id}/appeal")
def appeal(request_id: str, body: s.AppealInput, a: Actor = Depends(APPEALS), db: Session = Depends(get_db)):
    return _run(svc.appeal, db, a, _path_id(request_id, "request"), s.as_dict(body))


@router.post("/requests/{request_id}/appeal-decision")
def decide_appeal(
    request_id: str, body: s.AppealDecisionInput, a: Actor = Depends(APPEALS), db: Session = Depends(get_db)
):
    return _run(svc.decide_appeal, db, a, _path_id(request_id, "request"), s.as_dict(body))


@router.post("/requests/{request_id}/close")
def close_request(request_id: str, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.close_request, db, a, _path_id(request_id, "request"))


# ---------------------------------------------------------------- referrals


@router.get("/referrals")
def list_referrals(
    request_id: str | None = Query(None, max_length=64),
    status: Literal["open", "replied"] | None = None,
    cursor: str | None = Query(None, max_length=16),
    limit: int = LIMIT,
    a: Actor = Depends(REFERRALS),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_referrals,
        db,
        a,
        request_id=_uuid_query(request_id, "request_id"),
        status=status,
        cursor=cursor,
        limit=limit,
    )


@router.post("/referrals/{referral_id}/reply")
def reply_referral(
    referral_id: str, body: s.ReplyInput, a: Actor = Depends(RESPOND_TO_REFERRAL), db: Session = Depends(get_db)
):
    return _run(svc.reply_referral, db, a, _path_id(referral_id, "referral"), body.reply)


# ---------------------------------------------------------------- widget


@router.get("/stats/nearing-deadline")
def nearing_deadline(a: Actor = Depends(STATS), db: Session = Depends(get_db)):
    return _run(svc.nearing_deadline, db, a)
