"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/external-university-portals. Read-only: modules export,
send and import through the inter-institution-records port, never through this API. No transcript content is shown."""

from __future__ import annotations

from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..application import service
from .deps import Principal, require

router = APIRouter(tags=["external-university-portals"])
READ = "external-university-portals:exchange:read"
Status = Literal["prepared", "sent", "manual_action_required", "delivered_manually", "received", "parsed", "rejected"]


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"code": code, "detail": detail}, status_code=status_code)


@router.get("/exchanges")
def list_exchanges(
    partner_id: str | None = Query(default=None, max_length=60),
    direction: Literal["outbound", "inbound"] | None = None,
    status: Status | None = None,
    person_id: str | None = Query(default=None, pattern=service.UUID_RE.pattern, max_length=36),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    p: Principal = Depends(require(READ)),
    db: Session = Depends(get_db),
):
    try:
        return service.list_exchanges(
            db,
            partner_id=partner_id,
            direction=direction,
            status=status,
            person_id=person_id and person_id.lower(),
            cursor=cursor,
            limit=limit,
        )
    except service.InvalidCursorError:
        return _error(400, "invalid_cursor", "the cursor is not one this API issued")


@router.get("/exchanges/{id}")
def get_exchange(id: str, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    found = service.get_detail(db, id)
    if found is None:
        return _error(404, "not_found", "no such exchange")
    return found
