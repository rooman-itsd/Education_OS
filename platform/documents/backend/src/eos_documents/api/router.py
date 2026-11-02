"""FastAPI router for documents: upload intent, confirmation, download URLs, and lifecycle."""

from __future__ import annotations

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import DocumentError

router = APIRouter(tags=["documents"])

DOCUMENT_READ = "documents:document:read"
DOCUMENT_READ_ANY = "documents:document:read-any"
DOCUMENT_WRITE = "documents:document:write"
DOCUMENT_DELETE = "documents:document:delete"


def _is_elevated_reader(p: Principal) -> bool:
    return bool(p.super_admin or p.can(DOCUMENT_READ_ANY))


class UploadIntentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=255)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=64)
    client_token: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None


def _err(e: DocumentError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={"code": "document_error", "message": e.message})


@router.post("/upload-intent", status_code=201)
def request_upload_intent(
    body: UploadIntentInput,
    p: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        doc, created, url, exp = service.request_upload_intent(
            db,
            p.organisation_id,
            actor_id=p.user_id,
            filename=body.filename,
            mime_type=body.mime_type,
            size_bytes=body.size_bytes,
            title=body.title,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            client_token=body.client_token,
            tags=body.tags,
        )
        db.commit()
        resp_data = {
            "document": service.view_document(doc),
            "upload_url": url,
            "method": "PUT",
            "expires_in_seconds": exp,
        }
        return JSONResponse(resp_data, status_code=201 if created else 200)
    except DocumentError as e:
        db.rollback()
        raise _err(e) from e
    except IntegrityError:
        db.rollback()
        existing = service.find_by_token(db, p.organisation_id, body.client_token, uploaded_by=p.user_id)
        if existing:
            cfg = service.load_settings()
            store = service.get_storage(cfg)
            url = store.generate_upload_url(
                existing.bucket, existing.storage_path, existing.mime_type, cfg.url_expires_seconds
            )
            return JSONResponse(
                {
                    "document": service.view_document(existing),
                    "upload_url": url,
                    "method": "PUT",
                    "expires_in_seconds": cfg.url_expires_seconds,
                },
                status_code=200,
            )
        raise


@router.post("/{id}/confirm")
def confirm_upload(
    id: str,
    p: Principal = Depends(require(DOCUMENT_WRITE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        doc = service.confirm_upload(db, p.organisation_id, p.user_id, id)
        db.commit()
        return service.view_document(doc)
    except DocumentError as e:
        db.rollback()
        raise _err(e) from e


@router.get("/{id}/download-url")
def get_download_url(
    id: str,
    p: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    doc = service.get_document(db, p.organisation_id, id)
    if not doc or doc.status == service.STATUS_DELETED or (not _is_elevated_reader(p) and doc.uploaded_by != p.user_id):
        raise HTTPException(404, detail={"code": "not_found", "message": "Document not found"})
    try:
        doc, url, exp = service.get_download_url(db, p.organisation_id, p.user_id, id)
        return {
            "download_url": url,
            "filename": doc.filename,
            "expires_in_seconds": exp,
        }
    except DocumentError as e:
        raise _err(e) from e


@router.get("/{id}")
def get_document(
    id: str,
    p: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    doc = service.get_document(db, p.organisation_id, id)
    if not doc or doc.status == service.STATUS_DELETED or (not _is_elevated_reader(p) and doc.uploaded_by != p.user_id):
        raise HTTPException(404, detail={"code": "not_found", "message": "Document not found"})
    return service.view_document(doc)


@router.get("/")
def list_documents(
    status: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    uploaded_by: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require(DOCUMENT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    effective_uploaded_by = uploaded_by if _is_elevated_reader(p) else p.user_id
    items, total = service.list_documents(
        db,
        p.organisation_id,
        status=status,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=effective_uploaded_by,
        limit=limit,
        offset=offset,
    )
    return {"items": [service.view_document(d) for d in items], "total": total}


@router.delete("/{id}")
def delete_document(
    id: str,
    p: Principal = Depends(require(DOCUMENT_DELETE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        service.delete_document(db, p.organisation_id, p.user_id, id)
        db.commit()
        return {"deleted": True, "document_id": id}
    except DocumentError as e:
        db.rollback()
        raise _err(e) from e
