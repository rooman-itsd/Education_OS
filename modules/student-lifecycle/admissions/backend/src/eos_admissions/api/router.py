"""Routes from contracts/openapi.yaml, mounted by the host at /api/v1/admissions. Each staff route names the
permission key it needs; the service filters every query by the caller's organisation."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, AdmissionsError
from ..domain.enums import APPLICATION_STATUSES
from . import schemas as s
from .deps import (
    PERM_APPLICATION_MANAGE,
    PERM_APPLICATION_READ,
    PERM_DOCUMENT_VERIFY,
    PERM_MERIT_LIST_MANAGE,
    PERM_OFFER_MANAGE,
    PERM_REPORT_READ,
    PERM_SELF_READ,
    public_organisation,
    require,
)

router = APIRouter(tags=["admissions"])


def _run(db: Session, fn, *args: Any, conflict: tuple[str, str] | None = None, **kwargs: Any) -> Any:
    """Run a use case, commit, and turn refusals into the contract's {code, message} error body."""
    try:
        result = fn(db, *args, **kwargs)
        db.commit()
        return result
    except AdmissionsError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.to_dict()) from exc
    except IntegrityError as exc:
        # Two requests passed the same check at once; a unique index decided.
        db.rollback()
        code, message = conflict or ("conflict", "a record with the same unique value already exists")
        raise HTTPException(409, {"code": code, "message": message}) from exc


def _statuses(value: str | None) -> list[str] | None:
    """status is an array in form style without explode: status=eligible,offered."""
    if not value:
        return None
    statuses = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in statuses if v not in APPLICATION_STATUSES]
    if unknown:
        raise HTTPException(422, {"code": "invalid_status", "message": f"unknown status {', '.join(unknown)}"})
    return statuses


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value else None


# ---------------------------------------------------------------- applications


@router.get("/applications")
def list_applications(
    programme_id: UUID | None = None,
    academic_year: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(require(PERM_APPLICATION_READ)),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.list_applications,
        actor,
        programme_id=_uuid(programme_id),
        academic_year=academic_year,
        statuses=_statuses(status),
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/applications/{id}")
def get_application(id: str, actor: Actor = Depends(require(PERM_APPLICATION_READ)), db: Session = Depends(get_db)):
    return _run(db, svc.get_application, actor, id)


@router.put("/applications/{id}/status")
def change_status(
    id: str,
    body: s.StatusChangeInput,
    actor: Actor = Depends(require(PERM_APPLICATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.change_status, actor, id, body.status, body.reason)


@router.post("/applications/{id}/documents/{document_id}/verify")
def verify_document(
    id: str,
    document_id: str,
    body: s.DocumentVerificationInput,
    actor: Actor = Depends(require(PERM_DOCUMENT_VERIFY)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.verify_document, actor, id, document_id, body.verification_status, body.verification_note)


@router.post("/applications/{id}/offer", status_code=201)
def make_offer(
    id: str,
    body: s.OfferInput | None = None,
    actor: Actor = Depends(require(PERM_OFFER_MANAGE)),
    db: Session = Depends(get_db),
):
    body = body or s.OfferInput()
    return _run(
        db,
        svc.make_offer,
        actor,
        id,
        body.note,
        body.expires_at,
        conflict=("offer_already_exists", "Application already has an open offer"),
    )


# ---------------------------------------------------------------- merit lists


@router.get("/merit-lists")
def list_merit_lists(
    programme_id: UUID | None = None,
    academic_year: str | None = None,
    actor: Actor = Depends(require(PERM_MERIT_LIST_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.list_merit_lists, actor, programme_id=_uuid(programme_id), academic_year=academic_year)


@router.post("/merit-lists", status_code=201)
def generate_merit_list(
    body: s.MeritListInput,
    actor: Actor = Depends(require(PERM_MERIT_LIST_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.generate_merit_list,
        actor,
        programme_id=str(body.programme_id),
        academic_year=body.academic_year,
        title=body.title,
        scores=[(str(x.application_id), x.score) for x in body.scores],
    )


@router.get("/merit-lists/{id}")
def get_merit_list(id: str, actor: Actor = Depends(require(PERM_MERIT_LIST_MANAGE)), db: Session = Depends(get_db)):
    return _run(db, svc.get_merit_list, actor, id)


@router.post("/merit-lists/{id}/publish")
def publish_merit_list(id: str, actor: Actor = Depends(require(PERM_MERIT_LIST_MANAGE)), db: Session = Depends(get_db)):
    return _run(db, svc.publish_merit_list, actor, id)


# ---------------------------------------------------------------- reports and queues


@router.get("/reports/funnel")
def funnel_report(
    programme_id: UUID | None = None,
    academic_year: str | None = None,
    actor: Actor = Depends(require(PERM_REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.funnel_report, actor, programme_id=_uuid(programme_id), academic_year=academic_year)


@router.get("/documents")
def list_documents(
    verification_status: Literal["pending", "verified", "rejected"] = "pending",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(require(PERM_DOCUMENT_VERIFY)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.list_documents, actor, verification_status=verification_status, page=page, page_size=page_size)


# ---------------------------------------------------------------- signed-in applicant (own applications)


@router.get("/me/applications")
def my_applications(actor: Actor = Depends(require(PERM_SELF_READ)), db: Session = Depends(get_db)):
    return _run(db, svc.list_my_applications, actor)


@router.post("/me/applications")
def link_application(
    body: s.LinkApplicationInput,
    actor: Actor = Depends(require(PERM_SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.link_application, actor, body.reference_number, body.email)


# ---------------------------------------------------------------- public (anonymous, per organisation)
# No token: public_organisation takes the organisation the host resolved from org_slug, or answers 404.


@router.post("/public/{org_slug}/applications", status_code=201)
def submit_application(
    body: s.ApplicationInput, organisation_id: str = Depends(public_organisation), db: Session = Depends(get_db)
):
    a = body.applicant
    return _run(
        db,
        svc.submit,
        organisation_id,
        first_name=a.first_name,
        last_name=a.last_name,
        email=a.email,
        phone=a.phone,
        date_of_birth=a.date_of_birth,
        programme_id=str(body.programme_id),
        academic_year=body.academic_year,
        selection_process_round_id=_uuid(body.selection_process_round_id),
        portfolio_item_id=_uuid(body.portfolio_item_id),
    )


@router.get("/public/{org_slug}/applications/track")
def track_application(
    reference_number: str = Query(min_length=1, max_length=32),
    email: str = Query(min_length=3, max_length=320),
    organisation_id: str = Depends(public_organisation),
    db: Session = Depends(get_db),
):
    return _run(db, svc.track, organisation_id, reference_number, email)


@router.post("/public/{org_slug}/applications/{reference_number}/documents", status_code=201)
def attach_document(
    reference_number: str,
    body: s.ApplicationDocumentInput,
    organisation_id: str = Depends(public_organisation),
    db: Session = Depends(get_db),
):
    return _run(
        db,
        svc.attach_document,
        organisation_id,
        reference_number,
        email=body.email,
        type=body.type,
        document_id=body.document_id,
        label=body.label,
    )


@router.post("/public/{org_slug}/applications/{reference_number}/offer/accept")
def accept_offer(
    reference_number: str,
    body: s.OfferAcceptInput,
    organisation_id: str = Depends(public_organisation),
    db: Session = Depends(get_db),
):
    return _run(db, svc.accept_offer, organisation_id, reference_number, email=body.email)


@router.post("/public/{org_slug}/applications/{reference_number}/offer/decline")
def decline_offer(
    reference_number: str,
    body: s.OfferDeclineInput,
    organisation_id: str = Depends(public_organisation),
    db: Session = Depends(get_db),
):
    return _run(db, svc.decline_offer, organisation_id, reference_number, email=body.email, reason=body.reason)
