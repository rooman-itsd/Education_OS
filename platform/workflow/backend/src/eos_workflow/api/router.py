"""HTTP router for workflow: chains, requests, approvals, and delegation."""

from __future__ import annotations

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import WorkflowError
from ..domain.models import (
    MAX_CLIENT_TOKEN,
    MAX_CODE,
    MAX_ENTITY_ID,
    MAX_ENTITY_TYPE,
    MAX_ROLE,
    MAX_STEP_NAME,
    MAX_TITLE,
)

router = APIRouter(tags=["workflow"])

CHAIN_READ = "workflow:chain:read"
CHAIN_WRITE = "workflow:chain:write"
REQUEST_CREATE = "workflow:request:create"
REQUEST_READ = "workflow:request:read"
APPROVAL_ACTION = "workflow:approval:action"
PLATFORM_READ = "platform:workflow:read"
APPROVER_OR_ADMIN_PERMISSIONS = {APPROVAL_ACTION, CHAIN_WRITE, PLATFORM_READ}


def _is_elevated_reader(p: Principal) -> bool:
    return bool(p.super_admin or (p.permissions & APPROVER_OR_ADMIN_PERMISSIONS))


class NewStepInput(BaseModel):
    step_order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=MAX_STEP_NAME)
    approver_role: str = Field(min_length=1, max_length=MAX_ROLE)
    sla_hours: int | None = Field(default=None, ge=1)
    is_final: bool = False


class NewChainInput(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_CODE)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str | None = None
    steps: list[NewStepInput] = Field(min_length=1)


class NewRequestInput(BaseModel):
    chain_code: str = Field(min_length=1, max_length=MAX_CODE)
    entity_type: str = Field(min_length=1, max_length=MAX_ENTITY_TYPE)
    entity_id: str = Field(min_length=1, max_length=MAX_ENTITY_ID)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str | None = None
    client_token: str | None = Field(default=None, max_length=MAX_CLIENT_TOKEN)
    context: dict | None = None


class ActionInput(BaseModel):
    comments: str | None = None


class DelegateInput(BaseModel):
    delegate_to_user_id: str = Field(min_length=1)
    comments: str | None = None


def _err(e: WorkflowError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=str(e))


@router.get("/chains")
def list_chains(p: Principal = Depends(require(CHAIN_READ)), db: Session = Depends(get_db)):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    chains = service.list_chains(db, p.organisation_id)
    return [service.view_chain(c) for c in chains]


@router.post("/chains", status_code=201)
def create_chain(body: NewChainInput, p: Principal = Depends(require(CHAIN_WRITE)), db: Session = Depends(get_db)):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    try:
        chain = service.create_chain(
            db,
            p.organisation_id,
            code=body.code,
            title=body.title,
            description=body.description,
            steps_data=[s.model_dump() for s in body.steps],
        )
        db.commit()
        return service.view_chain(chain)
    except WorkflowError as e:
        db.rollback()
        raise _err(e) from e


@router.get("/chains/{id}")
def get_chain(id: str, p: Principal = Depends(require(CHAIN_READ)), db: Session = Depends(get_db)):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    chain = service.get_chain(db, p.organisation_id, id)
    if not chain:
        raise HTTPException(404, "Approval chain not found")
    return service.view_chain(chain)


@router.get("/requests")
def search_requests(
    status: str | None = None,
    entity_type: str | None = None,
    requester_id: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require(REQUEST_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    effective_requester_id = requester_id if _is_elevated_reader(p) else p.user_id
    items, total = service.list_requests(
        db,
        p.organisation_id,
        status=status,
        entity_type=entity_type,
        requester_id=effective_requester_id,
        limit=limit,
        offset=offset,
    )
    return {"items": [service.view_request(r) for r in items], "total": total}


@router.post("/requests", status_code=201)
def create_request(
    body: NewRequestInput, p: Principal = Depends(require(REQUEST_CREATE)), db: Session = Depends(get_db)
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    try:
        req, created = service.create_request(
            db,
            p.organisation_id,
            chain_code=body.chain_code,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            title=body.title,
            requester_id=p.user_id,
            requester_name=None,
            description=body.description,
            client_token=body.client_token,
            context_data=body.context,
        )
        db.commit()
        return JSONResponse(service.view_request(req), status_code=201 if created else 200)
    except WorkflowError as e:
        db.rollback()
        raise _err(e) from e
    except IntegrityError:
        db.rollback()
        existing = service.find_by_token(db, p.organisation_id, body.client_token)
        if existing:
            return JSONResponse(service.view_request(existing), status_code=200)
        raise


@router.get("/requests/pending")
def list_pending_approvals(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require(REQUEST_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    items, total = service.list_pending(
        db,
        p.organisation_id,
        user_id=p.user_id,
        user_roles=list(p.roles),
        limit=limit,
        offset=offset,
    )
    return {"items": [service.view_request(r) for r in items], "total": total}


@router.get("/requests/{id}")
def get_request(id: str, p: Principal = Depends(require(REQUEST_READ)), db: Session = Depends(get_db)):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    req = service.get_request(db, p.organisation_id, id)
    if not req or (not _is_elevated_reader(p) and req.requester_id != p.user_id):
        raise HTTPException(404, "Workflow request not found")
    return service.view_request_detail(req)


@router.post("/requests/{id}/approve")
def approve_request(
    id: str,
    body: ActionInput | None = None,
    p: Principal = Depends(require(APPROVAL_ACTION)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    comments = body.comments if body else None
    try:
        req = service.approve_request(
            db,
            p.organisation_id,
            request_id=id,
            actor_id=p.user_id,
            actor_roles=list(p.roles),
            comments=comments,
        )
        db.commit()
        return service.view_request(req)
    except WorkflowError as e:
        db.rollback()
        raise _err(e) from e


@router.post("/requests/{id}/reject")
def reject_request(
    id: str,
    body: ActionInput | None = None,
    p: Principal = Depends(require(APPROVAL_ACTION)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    comments = body.comments if body else None
    try:
        req = service.reject_request(
            db,
            p.organisation_id,
            request_id=id,
            actor_id=p.user_id,
            actor_roles=list(p.roles),
            comments=comments,
        )
        db.commit()
        return service.view_request(req)
    except WorkflowError as e:
        db.rollback()
        raise _err(e) from e


@router.post("/requests/{id}/delegate")
def delegate_request(
    id: str,
    body: DelegateInput,
    p: Principal = Depends(require(APPROVAL_ACTION)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, "organisation_id required")
    try:
        req = service.delegate_request(
            db,
            p.organisation_id,
            request_id=id,
            actor_id=p.user_id,
            delegate_to_user_id=body.delegate_to_user_id,
            actor_roles=list(p.roles),
            comments=body.comments,
        )
        db.commit()
        return service.view_request(req)
    except WorkflowError as e:
        db.rollback()
        raise _err(e) from e
