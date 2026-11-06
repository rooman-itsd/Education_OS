"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/government-portals. Read-only: modules prepare and file
through the regulatory-submission port, never through this API."""

from __future__ import annotations

from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..application import service
from ..infrastructure.config import Settings
from .deps import Principal, require

router = APIRouter(tags=["government-portals"])
READ = "government-portals:package:read"
Status = Literal["draft", "prepared", "invalid", "submitted", "uploaded_manually", "acknowledged", "superseded"]


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"code": code, "detail": detail}, status_code=status_code)


@router.get("/forms")
def list_forms(authority: Literal["aishe", "nirf", "naac"] | None = None, p: Principal = Depends(require(READ))):
    return service.list_forms(Settings.from_env(), authority).output


@router.get("/packages")
def list_packages(
    form_code: str | None = Query(default=None, max_length=64),
    period: str | None = Query(default=None, max_length=40),
    status: Status | None = None,
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    p: Principal = Depends(require(READ)),
    db: Session = Depends(get_db),
):
    try:
        return service.list_packages(db, form_code=form_code, period=period, status=status, cursor=cursor, limit=limit)
    except service.InvalidCursorError:
        return _error(400, "invalid_cursor", "the cursor is not one this API issued")


@router.get("/packages/{id}")
def get_package(id: str, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    found = service.get_detail(db, id)
    if found is None:
        return _error(404, "not_found", "no such package")
    return found
