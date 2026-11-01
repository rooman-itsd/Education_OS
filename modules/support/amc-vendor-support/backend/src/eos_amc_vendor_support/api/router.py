"""HTTP surface of amc-vendor-support, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/amc-vendor-support (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permission the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import AmcVendorSupportError
from ..domain.contracts import CONTRACT_STATUSES
from ..domain.engagements import ENGAGEMENT_KINDS, ENGAGEMENT_STATUSES
from ..infrastructure.config import MAX_WINDOW_DAYS, MIN_WINDOW_DAYS
from . import schemas as s
from .deps import require

router = APIRouter(tags=["amc-vendor-support"])

LIMIT = Query(20, ge=1, le=100)
READ = require(perm.CONTRACT_READ)
MANAGE = require(perm.CONTRACT_MANAGE)
ENGAGE = require(perm.ENGAGEMENT_MANAGE)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AmcVendorSupportError as e:
        raise HTTPException(e.status, e.body()) from e


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`status` is an array in form style without explode: status=draft,active."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise HTTPException(
            422, {"code": f"invalid_{field}", "message": f"unknown {field} {', '.join(unknown)}", "field": field}
        )
    return values


# ---------------------------------------------------------------- contracts


@router.get("/contracts")
def list_contracts(
    status: str | None = None,
    vendor_id: str | None = None,
    owner: str | None = None,
    expiring: bool | None = None,
    expired: bool | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_contracts,
        db,
        a,
        statuses=_listed(status, CONTRACT_STATUSES, "status"),
        vendor_id=vendor_id,
        owner=owner,
        expiring=expiring,
        expired=expired,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.post("/contracts", status_code=201)
def create_contract(body: s.ContractInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_contract, db, a, s.as_dict(body, partial=False))


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_contract, db, a, contract_id)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: str, body: s.ContractUpdateInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_contract, db, a, contract_id, s.as_dict(body, partial=True))


@router.post("/contracts/{contract_id}/activate")
def activate_contract(contract_id: str, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.activate_contract, db, a, contract_id)


@router.post("/contracts/{contract_id}/terminate")
def terminate_contract(
    contract_id: str, body: s.TerminateInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.terminate_contract, db, a, contract_id, s.as_dict(body, partial=False))


@router.post("/contracts/{contract_id}/renew", status_code=201)
def renew_contract(contract_id: str, body: s.RenewInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.renew_contract, db, a, contract_id, s.as_dict(body, partial=False))


@router.post("/contracts/{contract_id}/covered-items", status_code=201)
def add_covered_item(
    contract_id: str, body: s.CoveredItemInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.add_covered_item, db, a, contract_id, s.as_dict(body, partial=False))


@router.delete("/contracts/{contract_id}/covered-items/{item_id}", status_code=204)
def remove_covered_item(contract_id: str, item_id: str, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    _run(svc.remove_covered_item, db, a, contract_id, item_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- engagements


@router.get("/engagements")
def list_engagements(
    contract_id: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    within_terms: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    kinds = _listed(kind, ENGAGEMENT_KINDS, "kind")
    return _run(
        svc.list_engagements,
        db,
        a,
        contract_id=contract_id,
        statuses=_listed(status, ENGAGEMENT_STATUSES, "status"),
        kind=kinds[0] if kinds else None,
        within_terms=within_terms,
        cursor=cursor,
        limit=limit,
    )


@router.post("/engagements", status_code=201)
def raise_engagement(body: s.EngagementInput, a: Actor = Depends(ENGAGE), db: Session = Depends(get_db)):
    return _run(svc.raise_engagement, db, a, s.as_dict(body, partial=False))


@router.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: str, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_engagement, db, a, engagement_id)


@router.patch("/engagements/{engagement_id}")
def update_engagement(
    engagement_id: str, body: s.EngagementUpdateInput, a: Actor = Depends(ENGAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_engagement, db, a, engagement_id, s.as_dict(body, partial=True))


@router.post("/engagements/{engagement_id}/status")
def move_engagement(
    engagement_id: str, body: s.EngagementStatusInput, a: Actor = Depends(ENGAGE), db: Session = Depends(get_db)
):
    return _run(svc.move_engagement, db, a, engagement_id, s.as_dict(body, partial=False))


# ---------------------------------------------------------------- coverage and statistics


@router.get("/coverage")
def coverage(
    module: str,
    entity: str,
    id: str,
    include_expired: bool = False,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(svc.coverage, db, a, module, entity, id, include_expired)


@router.get("/stats/contracts-expiring")
def contracts_expiring(
    within_days: int | None = Query(None, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(svc.contracts_expiring_stats, db, a, within_days)
