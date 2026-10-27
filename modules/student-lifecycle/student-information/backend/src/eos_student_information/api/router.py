"""FastAPI router for student-information (SIS person system of record).

Mounts all routes described in contracts/openapi.yaml.
Strictly verifies permissions from contracts/permissions.yaml.
"""

from __future__ import annotations

from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import (
    PERM_DOCUMENT_MANAGE,
    PERM_ID_CARD_MANAGE,
    PERM_PERSON_READ,
    PERM_PERSON_WRITE,
    PERM_STATUS_MANAGE,
    require,
)

router = APIRouter(tags=["student-information"])


VALID_STATUSES = {"pending", "active", "suspended", "graduated", "withdrawn", "alumnus"}


def _parse_statuses(value: str | None) -> list[str] | None:
    """`status` is an array in form style without explode: status=active,pending."""
    if not value:
        return None
    statuses = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in statuses if v not in VALID_STATUSES]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_status", "message": f"unknown status {', '.join(unknown)}", "field": "status"},
        )
    return statuses


def _run(fn, *args: Any, **kwargs: Any) -> Any:
    """Runs service function, commits on success, and maps ServiceError to contract-compatible HTTPException."""
    try:
        res = fn(*args, **kwargs)
        for arg in args:
            if isinstance(arg, Session):
                arg.commit()
                break
        else:
            if "db" in kwargs and isinstance(kwargs["db"], Session):
                kwargs["db"].commit()
        return res
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


# ---------------------------------------------------------------- Person CRUD & Search


@router.get("/people", status_code=200)
def list_people(
    q: str | None = None,
    identity_number: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(require(PERM_PERSON_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Finds people in caller's organisation with exact identity match, search, and status filter."""
    parsed_status = _parse_statuses(status)
    return _run(
        svc.list_people,
        db,
        actor,
        q=q,
        identity_number=identity_number,
        status=parsed_status,
        page=page,
        page_size=page_size,
    )


@router.post("/people", status_code=201)
def create_person(
    body: s.PersonInput,
    actor: Actor = Depends(require(PERM_PERSON_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Creates a new person record in pending status."""
    return _run(svc.create_person, db, actor, s.dump(body)).to_dict()


@router.get("/people/{id}", status_code=200)
def get_person(
    id: str,
    actor: Actor = Depends(require(PERM_PERSON_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves one person record by id within the caller's organisation."""
    return _run(svc.get_person, db, actor, id).to_dict()


@router.patch("/people/{id}", status_code=200)
def update_person(
    id: str,
    body: s.PersonUpdate,
    actor: Actor = Depends(require(PERM_PERSON_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Updates profile fields (does not change status)."""
    return _run(svc.update_person, db, actor, id, s.dump(body)).to_dict()


# ---------------------------------------------------------------- Status History & Transition


@router.get("/people/{id}/status", status_code=200)
def get_status_history(
    id: str,
    actor: Actor = Depends(require(PERM_PERSON_READ)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieves full status history for one person, most recent first."""
    return _run(svc.get_status_history, db, actor, id)


@router.put("/people/{id}/status", status_code=200)
def change_status(
    id: str,
    body: s.StatusChangeInput,
    actor: Actor = Depends(require(PERM_STATUS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Changes person status with a reason and appends to immutable history."""
    return _run(
        svc.change_status,
        db,
        actor,
        id,
        status=body.status,
        reason=body.reason,
        effective_date=body.effective_date,
    ).to_dict()


# ---------------------------------------------------------------- Document References


@router.get("/people/{id}/documents", status_code=200)
def list_documents(
    id: str,
    actor: Actor = Depends(require(PERM_PERSON_READ)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists document references attached to a person."""
    return _run(svc.list_documents, db, actor, id)


@router.post("/people/{id}/documents", status_code=201)
def attach_document(
    id: str,
    body: s.PersonDocumentInput,
    actor: Actor = Depends(require(PERM_DOCUMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Attaches a document reference stored in platform/documents."""
    return _run(svc.attach_document, db, actor, id, s.dump(body)).to_dict()


@router.delete("/people/{id}/documents/{document_id}", status_code=204)
def delete_document(
    id: str,
    document_id: str,
    actor: Actor = Depends(require(PERM_DOCUMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> Response:
    """Removes a document reference from a person's record."""
    _run(svc.delete_document, db, actor, id, document_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- Identity Cards


@router.get("/people/{id}/id-cards", status_code=200)
def list_id_cards(
    id: str,
    actor: Actor = Depends(require(PERM_PERSON_READ)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists ID cards issued to a person, most recent first."""
    return _run(svc.list_id_cards, db, actor, id)


@router.post("/people/{id}/id-cards", status_code=201)
def issue_id_card(
    id: str,
    body: s.IdentityCardInput | None = None,
    actor: Actor = Depends(require(PERM_ID_CARD_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Issues a new logical ID card for a person."""
    input_data = s.dump(body) if body else None
    return _run(svc.issue_id_card, db, actor, id, input_data).to_dict()


@router.post("/id-cards/{id}/revoke", status_code=200)
def revoke_id_card(
    id: str,
    body: s.RevokeCardInput,
    actor: Actor = Depends(require(PERM_ID_CARD_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Revokes an issued card with a reason."""
    return _run(svc.revoke_id_card, db, actor, id, body.reason).to_dict()
