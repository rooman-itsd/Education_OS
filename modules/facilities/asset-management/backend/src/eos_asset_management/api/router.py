"""HTTP surface of asset-management, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/asset-management. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, AssetError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["asset-management"])

PAGE = Query(1, ge=1)
PAGE_SIZE = Query(50, ge=1, le=200)
STATUSES = {"in_service", "in_repair", "idle", "missing", "disposal_pending", "disposed"}
CycleStatus = Literal["planned", "in_progress", "closed"]
LineResult = Literal["pending", "found", "missing", "damaged", "relocated"]
DisposalStatus = Literal["requested", "approved", "rejected", "completed", "cancelled"]


def _run(fn, *args):
    try:
        return fn(*args)
    except AssetError as e:
        raise HTTPException(e.status, e.body()) from e


def _csv(value: str | None, allowed: set[str], name: str) -> list[str] | None:
    """status is a comma-separated list (style: form, explode: false)."""
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in items if v not in allowed]
    if bad:
        raise HTTPException(422, {"code": "invalid_query", "message": f"unknown {name}: {', '.join(bad)}"})
    return items


# ---------------------------------------------------------------- categories


@router.get("/categories")
def list_categories(_: Actor = Depends(require(svc.ASSET_READ)), db: Session = Depends(get_db)):
    return svc.list_categories(db)


@router.post("/categories", status_code=201)
def create_category(body: s.CategoryIn, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_category, db, a, s.dump(body))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str,
    body: s.CategoryPatch,
    a: Actor = Depends(require(svc.ASSET_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_category, db, a, category_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- assets


@router.get("/assets")
def list_assets(
    category_id: str | None = None,
    status: str | None = Query(None, description="Comma-separated AssetStatus values"),
    org_unit_id: str | None = None,
    custodian_id: str | None = None,
    location: str | None = None,
    verification_due_before: date | None = None,
    warranty_expires_before: date | None = None,
    q: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.ASSET_READ)),
    db: Session = Depends(get_db),
):
    query = {
        "category_id": category_id,
        "status": _csv(status, STATUSES, "status"),
        "org_unit_id": org_unit_id,
        "custodian_id": custodian_id,
        "location": location,
        "verification_due_before": verification_due_before,
        "warranty_expires_before": warranty_expires_before,
        "q": q,
    }
    return _run(svc.list_assets, db, a, query, page, page_size)


@router.post("/assets", status_code=201)
def register_asset(body: s.AssetIn, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.register_asset, db, a, s.dump(body))


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, a: Actor = Depends(require(svc.ASSET_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_asset, db, a, asset_id)


@router.patch("/assets/{asset_id}")
def update_asset(
    asset_id: str, body: s.AssetPatch, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_asset, db, a, asset_id, s.dump(body, partial=True))


@router.put("/assets/{asset_id}/status")
def set_status(
    asset_id: str, body: s.StatusIn, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.set_status, db, a, asset_id, body.status, body.condition, body.reason)


@router.get("/assets/{asset_id}/transfers")
def list_transfers(asset_id: str, a: Actor = Depends(require(svc.ASSET_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_transfers, db, a, asset_id)


@router.post("/assets/{asset_id}/transfers", status_code=201)
def transfer_asset(
    asset_id: str, body: s.TransferIn, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.transfer_asset, db, a, asset_id, body.model_dump(exclude_unset=True))


@router.get("/assets/{asset_id}/depreciation")
def depreciation_schedule(
    asset_id: str, a: Actor = Depends(require(svc.DEPRECIATION_READ)), db: Session = Depends(get_db)
):
    return _run(svc.depreciation_schedule, db, a, asset_id)


# ---------------------------------------------------------------- verification


@router.get("/verifications/due")
def verifications_due(
    within_days: int | None = Query(None, ge=0),
    org_unit_id: str | None = None,
    a: Actor = Depends(require(svc.ASSET_READ)),
    db: Session = Depends(get_db),
):
    return svc.verifications_due(db, a, within_days, org_unit_id)


@router.get("/verification-cycles")
def list_cycles(
    status: CycleStatus | None = None,
    _: Actor = Depends(require(svc.VERIFY_PERFORM)),
    db: Session = Depends(get_db),
):
    return svc.list_cycles(db, status)


@router.post("/verification-cycles", status_code=201)
def create_cycle(body: s.CycleIn, a: Actor = Depends(require(svc.VERIFY_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_cycle, db, a, s.dump(body))


@router.get("/verification-cycles/{cycle_id}")
def get_cycle(cycle_id: str, _: Actor = Depends(require(svc.VERIFY_PERFORM)), db: Session = Depends(get_db)):
    return _run(svc.get_cycle, db, cycle_id)


@router.post("/verification-cycles/{cycle_id}/start")
def start_cycle(cycle_id: str, a: Actor = Depends(require(svc.VERIFY_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.start_cycle, db, a, cycle_id)


@router.get("/verification-cycles/{cycle_id}/lines")
def list_lines(
    cycle_id: str,
    result: LineResult | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    _: Actor = Depends(require(svc.VERIFY_PERFORM)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_lines, db, cycle_id, result, page, page_size)


@router.post("/verification-cycles/{cycle_id}/lines")
def record_lines(
    cycle_id: str,
    body: list[s.LineIn] = Body(min_length=1),
    a: Actor = Depends(require(svc.VERIFY_PERFORM)),
    db: Session = Depends(get_db),
):
    return _run(svc.record_lines, db, a, cycle_id, [x.model_dump() for x in body])


@router.post("/verification-cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: str,
    body: s.CloseIn | None = Body(default=None),
    a: Actor = Depends(require(svc.VERIFY_MANAGE)),
    db: Session = Depends(get_db),
):
    body = body or s.CloseIn()
    return _run(svc.close_cycle, db, a, cycle_id, body.close_with_pending, body.note)


# ---------------------------------------------------------------- depreciation


@router.get("/depreciation-runs")
def list_runs(_: Actor = Depends(require(svc.DEPRECIATION_READ)), db: Session = Depends(get_db)):
    return svc.list_runs(db)


@router.post("/depreciation-runs", status_code=202)
def calculate_run(body: s.RunIn, a: Actor = Depends(require(svc.DEPRECIATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.calculate_run, db, a, body.period_end, body.category_ids)


@router.get("/depreciation-runs/{run_id}")
def get_run(run_id: str, _: Actor = Depends(require(svc.DEPRECIATION_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_run, db, run_id)


@router.delete("/depreciation-runs/{run_id}", status_code=204)
def delete_run(run_id: str, a: Actor = Depends(require(svc.DEPRECIATION_MANAGE)), db: Session = Depends(get_db)):
    _run(svc.delete_run, db, a, run_id)
    return Response(status_code=204)


@router.get("/depreciation-runs/{run_id}/lines")
def list_run_lines(
    run_id: str,
    category_id: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    _: Actor = Depends(require(svc.DEPRECIATION_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_run_lines, db, run_id, category_id, page, page_size)


@router.post("/depreciation-runs/{run_id}/post")
def post_run(run_id: str, a: Actor = Depends(require(svc.DEPRECIATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.post_run, db, a, run_id)


# ---------------------------------------------------------------- disposal


@router.get("/disposals")
def list_disposals(
    status: DisposalStatus | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.DISPOSAL_REQUEST, svc.DISPOSAL_APPROVE)),
    db: Session = Depends(get_db),
):
    return svc.list_disposals(db, a, status, page, page_size)


@router.post("/disposals", status_code=201)
def request_disposal(
    body: s.DisposalIn, a: Actor = Depends(require(svc.DISPOSAL_REQUEST)), db: Session = Depends(get_db)
):
    return _run(svc.request_disposal, db, a, s.dump(body))


@router.get("/disposals/{disposal_id}")
def get_disposal(
    disposal_id: str,
    a: Actor = Depends(require(svc.DISPOSAL_REQUEST, svc.DISPOSAL_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_disposal, db, a, disposal_id)


@router.post("/disposals/{disposal_id}/approve")
def approve_disposal(
    disposal_id: str,
    body: s.DecisionIn | None = Body(default=None),
    a: Actor = Depends(require(svc.DISPOSAL_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_disposal, db, a, disposal_id, True, body.note if body else None)


@router.post("/disposals/{disposal_id}/reject")
def reject_disposal(
    disposal_id: str, body: s.RejectIn, a: Actor = Depends(require(svc.DISPOSAL_APPROVE)), db: Session = Depends(get_db)
):
    return _run(svc.decide_disposal, db, a, disposal_id, False, body.reason)


@router.post("/disposals/{disposal_id}/cancel")
def cancel_disposal(
    disposal_id: str,
    a: Actor = Depends(require(svc.DISPOSAL_REQUEST, svc.DISPOSAL_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_disposal, db, a, disposal_id)


@router.post("/disposals/{disposal_id}/complete")
def complete_disposal(
    disposal_id: str, body: s.CompletionIn, a: Actor = Depends(require(svc.ASSET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.complete_disposal, db, a, disposal_id, s.dump(body))


# ---------------------------------------------------------------- summary


@router.get("/summary")
def summary(_: Actor = Depends(require(svc.ASSET_READ_ALL)), db: Session = Depends(get_db)):
    return svc.summary(db)
