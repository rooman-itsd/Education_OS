"""HTTP surface of regulatory-reports, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/regulatory-reports (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permissions the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import RegulatoryReportsError
from ..domain.filings import FILING_STATUSES
from ..infrastructure.models import AUTHORITY_LEN, TITLE_LEN
from . import schemas as s
from .deps import no_nul, require

router = APIRouter(tags=["regulatory-reports"], dependencies=[Depends(no_nul)])

LIMIT = Query(20, ge=1, le=100)
OBLIGATIONS_READ = require(perm.DATA_READ, perm.OBLIGATION_MANAGE, perm.FILING_PREPARE)
OBLIGATIONS_MANAGE = require(perm.OBLIGATION_MANAGE)
FILINGS_READ = require(perm.DATA_READ, perm.FILING_MANAGE, perm.FILING_PREPARE)
FILINGS_WORK = require(perm.FILING_PREPARE, perm.FILING_MANAGE)
FILINGS_MANAGE = require(perm.FILING_MANAGE)
STATS = require(perm.STATS_READ)
CALENDAR = require(perm.DATA_READ)  # stats:read too; the use case checks both
UUID = re.compile(s.UUID_PATTERN)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RegulatoryReportsError as e:
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


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`status` is an array in form style without explode: status=open,in_preparation."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise HTTPException(
            422, {"code": f"invalid_{field}", "message": f"unknown {field} {', '.join(unknown)}", "field": field}
        )
    return values


# ---------------------------------------------------------------- obligations


@router.get("/obligations")
def list_obligations(
    authority: str | None = Query(None, max_length=AUTHORITY_LEN),
    active: bool | None = None,
    q: str | None = Query(None, max_length=TITLE_LEN),
    a: Actor = Depends(OBLIGATIONS_READ),
    db: Session = Depends(get_db),
):
    return _run(svc.list_obligations, db, a, authority=authority, active=active, q=q)


@router.post("/obligations", status_code=201)
def create_obligation(body: s.ObligationInput, a: Actor = Depends(OBLIGATIONS_MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_obligation, db, a, s.as_dict(body, partial=False))


@router.get("/obligations/{obligation_id}")
def get_obligation(obligation_id: str, a: Actor = Depends(OBLIGATIONS_READ), db: Session = Depends(get_db)):
    return _run(svc.get_obligation, db, a, _path_id(obligation_id, "obligation"))


@router.patch("/obligations/{obligation_id}")
def update_obligation(
    obligation_id: str,
    body: s.ObligationUpdateInput,
    a: Actor = Depends(OBLIGATIONS_MANAGE),
    db: Session = Depends(get_db),
):
    return _run(svc.update_obligation, db, a, _path_id(obligation_id, "obligation"), s.as_dict(body, partial=True))


@router.post("/obligations/{obligation_id}/filings", status_code=201)
def create_filing(
    obligation_id: str, body: s.FilingInput, a: Actor = Depends(FILINGS_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.create_filing, db, a, _path_id(obligation_id, "obligation"), s.as_dict(body, partial=False))


# ---------------------------------------------------------------- filings


@router.get("/filings")
def list_filings(
    obligation_id: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    overdue: bool | None = None,
    due_before: date | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(FILINGS_READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_filings,
        db,
        a,
        obligation_id=_uuid_query(obligation_id, "obligation_id"),
        statuses=_listed(status, FILING_STATUSES, "status"),
        owner=_owner(owner),
        overdue=overdue,
        due_before=due_before,
        cursor=cursor,
        limit=limit,
    )


@router.get("/filings/{filing_id}")
def get_filing(filing_id: str, a: Actor = Depends(FILINGS_READ), db: Session = Depends(get_db)):
    return _run(svc.get_filing, db, a, _path_id(filing_id, "filing"))


@router.patch("/filings/{filing_id}")
def update_filing(
    filing_id: str, body: s.FilingUpdateInput, a: Actor = Depends(FILINGS_WORK), db: Session = Depends(get_db)
):
    return _run(svc.update_filing, db, a, _path_id(filing_id, "filing"), s.as_dict(body, partial=True))


@router.post("/filings/{filing_id}/status")
def move_filing(
    filing_id: str, body: s.FilingStatusInput, a: Actor = Depends(FILINGS_WORK), db: Session = Depends(get_db)
):
    return _run(svc.move_filing, db, a, _path_id(filing_id, "filing"), s.as_dict(body, partial=False))


@router.post("/filings/{filing_id}/submit")
def submit_filing(
    filing_id: str, body: s.SubmitInput, a: Actor = Depends(FILINGS_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.submit_filing, db, a, _path_id(filing_id, "filing"), s.as_dict(body, partial=False))


@router.post("/filings/{filing_id}/acknowledge")
def acknowledge_filing(
    filing_id: str, body: s.AcknowledgeInput, a: Actor = Depends(FILINGS_MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.acknowledge_filing, db, a, _path_id(filing_id, "filing"), s.as_dict(body, partial=False))


# ---------------------------------------------------------------- widgets


@router.get("/stats/due")
def due_stats(
    scope: Literal["mine", "all"] = "mine",
    a: Actor = Depends(STATS),
    db: Session = Depends(get_db),
):
    return _run(svc.due_stats, db, a, scope)


@router.get("/calendar")
def calendar(
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    a: Actor = Depends(CALENDAR),
    db: Session = Depends(get_db),
):
    return _run(svc.calendar, db, a, start, end)
