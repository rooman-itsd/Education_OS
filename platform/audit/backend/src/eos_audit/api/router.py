"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/audit (once apps/backend includes it).

There is no PUT, PATCH or DELETE on a record, and there never will be. `POST /records/export` is not served
yet: the contract delivers an export through platform/documents (#84), which does not exist.
"""

from __future__ import annotations

from datetime import datetime

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import AuditError
from ..domain.models import MAX_ACTION, MAX_CLIENT_TOKEN, MAX_ENTITY_ID, MAX_ENTITY_TYPE, MAX_MODULE, MAX_SUMMARY

router = APIRouter(tags=["audit"])

WRITE = "audit:record:write"
READ = "audit:record:read"
PLATFORM_READ = "platform:audit:read"


class NewRecord(BaseModel):
    client_token: str | None = Field(default=None, max_length=MAX_CLIENT_TOKEN)
    module: str = Field(min_length=1, max_length=MAX_MODULE)
    action: str = Field(min_length=1, max_length=MAX_ACTION)
    entity_type: str = Field(min_length=1, max_length=MAX_ENTITY_TYPE)
    entity_id: str = Field(min_length=1, max_length=MAX_ENTITY_ID)
    summary: str | None = Field(default=None, max_length=MAX_SUMMARY)
    before: dict | None = None
    after: dict | None = None
    context: dict | None = None


def _err(e: AuditError) -> HTTPException:
    return HTTPException(e.status, str(e))


def _reading_scope(p: Principal, requested: str | None) -> str | None:
    """An organisation user reads only their organisation; `organisation_id` is ignored for them, as the
    contract says. A caller with no organisation is the platform and needs platform:audit:read: without
    `organisation_id` they see platform-level records, with it, that organisation's."""
    if p.organisation_id:
        return p.organisation_id
    if not p.can(PLATFORM_READ):
        raise HTTPException(403, f"requires {PLATFORM_READ}")
    return requested


@router.post("/records", status_code=201)
def record_action(body: NewRecord, p: Principal = Depends(require(WRITE)), db: Session = Depends(get_db)):
    context = dict(body.context or {})
    # Who was really acting comes from the token alone. A value in the body is dropped, not trusted: otherwise
    # any writer could pin an action on a super admin, or hide that one was impersonating.
    context.pop("impersonated_by", None)
    if p.impersonated_by:
        context["impersonated_by"] = p.impersonated_by
    try:
        rec, created = service.record(
            db, organisation_id=p.organisation_id, actor=p.user_id, **body.model_dump(exclude={"context"}),
            context=context,
        )  # fmt: skip
        db.commit()
    except AuditError as e:
        raise _err(e) from e
    except IntegrityError:
        # Two requests with one client_token raced; the other one committed first. Return its record.
        db.rollback()
        rec, created = service.find_by_token(db, p.organisation_id, body.client_token), False
        if rec is None:
            raise
    return JSONResponse(service.view(db, rec), status_code=201 if created else 200)


@router.get("/records")
def search_records(
    module: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    organisation_id: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require(READ)),
    db: Session = Depends(get_db),
):
    scope = _reading_scope(p, organisation_id)
    result = service.search(
        db, organisation_id=scope, module=module, action=action, actor=actor, entity_type=entity_type,
        entity_id=entity_id, occurred_from=occurred_from, occurred_to=occurred_to, limit=limit, offset=offset,
    )  # fmt: skip
    if scope and scope != p.organisation_id:
        service.record_cross_organisation_read(db, actor=p.user_id, organisation_id=scope, what="search")
        db.commit()
    return result


@router.get("/records/{record_id}")
def get_record(record_id: str, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    _reading_scope(p, None)
    platform = not p.organisation_id
    try:
        rec = service.get_record(db, organisation_id=p.organisation_id, record_id=record_id, any_organisation=platform)
    except AuditError as e:
        raise _err(e) from e
    out = service.view(db, rec)
    if platform and rec.organisation_id:
        service.record_cross_organisation_read(db, actor=p.user_id, organisation_id=rec.organisation_id, what="record")
        db.commit()
    return out


@router.get("/entities/{entity_type}/{entity_id}/history")
def entity_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require(READ)),
    db: Session = Depends(get_db),
):
    scope = _reading_scope(p, None)
    return service.history(
        db, organisation_id=scope, entity_type=entity_type, entity_id=entity_id, limit=limit, offset=offset
    )
