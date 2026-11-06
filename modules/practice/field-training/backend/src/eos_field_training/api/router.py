"""HTTP surface of field-training, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/field-training. Handlers only map HTTP to the use cases in application/service.py; each declares the
permission the contract names for it. Where the contract allows one of several keys, the use case narrows what the
caller sees by which key they hold."""

from __future__ import annotations

from typing import Annotated, Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import AfterValidator
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, FieldTrainingError
from . import schemas as s
from .deps import require


def no_nul(request: Request) -> None:
    """Postgres text cannot hold a NUL character, so one never reaches a query: in the path the record cannot exist
    (404); in the query string the request is malformed (422). Bodies are checked by schemas.Strict."""
    if any("\x00" in v for v in request.path_params.values()):
        raise HTTPException(404, {"code": "not_found", "message": "not found in your organisation"})
    if any("\x00" in k or "\x00" in v for k, v in request.query_params.multi_items()):
        raise HTTPException(422, {"code": "invalid_query", "message": "the query string contains a NUL character"})


router = APIRouter(tags=["field-training"], dependencies=[Depends(no_nul)])

# The contract types every id as format: uuid; a malformed one in the path or a filter is a 422.
UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
LIMIT = Query(20, ge=1, le=100)
CURSOR = Query(None, max_length=100)
OpeningStatus = Literal["draft", "open", "closed", "cancelled"]
PlacementStatus = Literal["requested", "assigned", "active", "completed", "rejected", "withdrawn"]


# Ids are compared in lowercase everywhere (see schemas.LowerId): a path id or a filter in capitals names the same
# record as one in lowercase. (A parameter object is shared between handlers here, which is safe: FastAPI copies it.)
PathId = Annotated[str, Path(pattern=UUID), AfterValidator(str.lower)]
FilterId = Annotated[str | None, Query(pattern=UUID), AfterValidator(lambda v: None if v is None else v.lower())]


def _run(fn, *args):
    try:
        return fn(*args)
    except FieldTrainingError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- sites


@router.get("/sites")
def list_sites(
    active: bool | None = None,
    q: str | None = Query(None, max_length=200),
    _: Actor = Depends(require(svc.SITE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_sites(db, active, q)


@router.post("/sites", status_code=201)
def create_site(body: s.SiteIn, a: Actor = Depends(require(svc.SITE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_site, db, a, s.dump(body))


@router.get("/sites/{site_id}")
def get_site(site_id: PathId, _: Actor = Depends(require(svc.SITE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_site, db, site_id)


@router.patch("/sites/{site_id}")
def update_site(
    body: s.SiteIn, site_id: PathId, a: Actor = Depends(require(svc.SITE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_site, db, a, site_id, s.dump(body))


# ---------------------------------------------------------------- openings


@router.get("/openings")
def list_openings(
    status: OpeningStatus | None = None,
    site_id: FilterId = None,
    has_seats: bool | None = None,
    starts_after: s.Day | None = None,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(require(svc.OPENING_READ, svc.SUPERVISION_READ, svc.SELF_APPLY)),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "site_id": site_id, "has_seats": has_seats, "starts_after": starts_after}
    return svc.list_openings(db, a, filters, cursor, limit)


@router.post("/openings", status_code=201)
def create_opening(body: s.OpeningIn, a: Actor = Depends(require(svc.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_opening, db, a, s.dump(body))


@router.get("/openings/{opening_id}")
def get_opening(
    opening_id: PathId,
    a: Actor = Depends(require(svc.OPENING_READ, svc.SUPERVISION_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_opening, db, a, opening_id)


@router.patch("/openings/{opening_id}")
def update_opening(
    body: s.OpeningIn,
    opening_id: PathId,
    a: Actor = Depends(require(svc.OPENING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_opening, db, a, opening_id, s.dump(body))


@router.post("/openings/{opening_id}/publish")
def publish_opening(opening_id: PathId, a: Actor = Depends(require(svc.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.publish_opening, db, a, opening_id)


@router.post("/openings/{opening_id}/close")
def close_opening(opening_id: PathId, a: Actor = Depends(require(svc.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.close_opening, db, a, opening_id)


@router.post("/openings/{opening_id}/cancel")
def cancel_opening(
    body: s.ReasonIn,
    opening_id: PathId,
    a: Actor = Depends(require(svc.OPENING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_opening, db, a, opening_id, body.reason)


@router.post("/openings/{opening_id}/apply", status_code=201)
def apply(
    *,
    body: s.ApplyIn | None = None,
    opening_id: PathId,
    a: Actor = Depends(require(svc.SELF_APPLY)),
    db: Session = Depends(get_db),
):
    return _run(svc.apply, db, a, opening_id, body.statement if body else None)


# ---------------------------------------------------------------- placements


@router.get("/placements")
def list_placements(
    status: PlacementStatus | None = None,
    opening_id: FilterId = None,
    site_id: FilterId = None,
    trainee_id: FilterId = None,
    supervisor_id: FilterId = None,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(require(svc.PLACEMENT_READ, svc.SUPERVISION_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "status": status,
        "opening_id": opening_id,
        "site_id": site_id,
        "trainee_id": trainee_id,
        "supervisor_id": supervisor_id,
    }
    return svc.list_placements(db, a, filters, cursor, limit)


@router.post("/placements", status_code=201)
def assign_placement(
    body: s.AssignIn, a: Actor = Depends(require(svc.PLACEMENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.assign_placement, db, a, s.dump(body))


@router.get("/placements/{placement_id}")
def get_placement(
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_READ, svc.SUPERVISION_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_placement, db, a, placement_id)


@router.patch("/placements/{placement_id}")
def update_placement(
    body: s.PlacementPatchIn,
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_placement, db, a, placement_id, s.dump(body))


@router.post("/placements/{placement_id}/decision")
def decide(
    body: s.DecisionIn,
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide, db, a, placement_id, body.model_dump())


@router.post("/placements/{placement_id}/start")
def start_placement(
    placement_id: PathId, a: Actor = Depends(require(svc.PLACEMENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.start_placement, db, a, placement_id)


@router.post("/placements/{placement_id}/complete")
def complete_placement(
    *,
    body: s.CompleteIn | None = None,
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    body = body or s.CompleteIn()
    return _run(svc.complete_placement, db, a, placement_id, body.override, body.reason)


@router.post("/placements/{placement_id}/withdraw")
def withdraw_placement(
    body: s.ReasonIn,
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_MANAGE, svc.SELF_APPLY)),
    db: Session = Depends(get_db),
):
    return _run(svc.withdraw_placement, db, a, placement_id, body.reason)


# ---------------------------------------------------------------- logbook


@router.get("/placements/{placement_id}/logs")
def list_logs(
    placement_id: PathId,
    status: Literal["submitted", "verified", "returned"] | None = None,
    a: Actor = Depends(require(svc.PLACEMENT_READ, svc.SUPERVISION_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_logs, db, a, placement_id, status)


@router.post("/placements/{placement_id}/logs", status_code=201)
def add_log(
    body: s.LogEntryIn,
    placement_id: PathId,
    a: Actor = Depends(require(svc.SELF_LOG)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_log, db, a, placement_id, s.dump(body))


@router.patch("/logs/{log_id}")
def edit_log(
    body: s.LogEntryIn, log_id: PathId, a: Actor = Depends(require(svc.SELF_LOG)), db: Session = Depends(get_db)
):
    return _run(svc.edit_log, db, a, log_id, s.dump(body))


@router.post("/logs/{log_id}/verify")
def verify_log(log_id: PathId, a: Actor = Depends(require(svc.LOG_VERIFY)), db: Session = Depends(get_db)):
    return _run(svc.verify_log, db, a, log_id)


@router.post("/logs/{log_id}/return")
def return_log(
    body: s.ReasonIn, log_id: PathId, a: Actor = Depends(require(svc.LOG_VERIFY)), db: Session = Depends(get_db)
):
    return _run(svc.return_log, db, a, log_id, body.reason)


# ---------------------------------------------------------------- assessments


@router.get("/placements/{placement_id}/assessments")
def list_assessments(
    placement_id: PathId,
    a: Actor = Depends(require(svc.PLACEMENT_READ, svc.SUPERVISION_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_assessments, db, a, placement_id)


@router.post("/placements/{placement_id}/assessments", status_code=201)
def record_assessment(
    body: s.AssessmentIn,
    placement_id: PathId,
    a: Actor = Depends(require(svc.ASSESSMENT_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(svc.record_assessment, db, a, placement_id, s.dump(body))


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/placements")
def my_placements(
    include_past: bool = False, a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)
):
    return svc.my_placements(db, a, include_past)


@router.get("/me/hours")
def my_hours(placement_id: FilterId = None, a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return _run(svc.my_hours, db, a, placement_id)


@router.get("/me/trainees")
def my_trainees(limit: int = LIMIT, a: Actor = Depends(require(svc.SUPERVISION_READ)), db: Session = Depends(get_db)):
    return svc.my_trainees(db, a, limit)
