from __future__ import annotations

from eos_core.db import get_db
from eos_core.settings import settings
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import TenancyError

router = APIRouter(tags=["tenancy"])


def _err(e: TenancyError):
    return HTTPException(e.status, str(e))


class AdminUser(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)


class RegistrationRequest(BaseModel):
    organisation_name: str = Field(min_length=2, max_length=200)
    slug: str
    academy_type: str
    country: str | None = None
    admin: AdminUser
    accepted_terms: bool = False


class Verify(BaseModel):
    token: str


class Toggle(BaseModel):
    enabled: bool


class StatusChange(BaseModel):
    status: str
    reason: str


class Overrides(BaseModel):
    grant_modules: list[str] = []
    revoke_modules: list[str] = []
    reason: str = ""


class PackageRequest(BaseModel):
    academy_type: str


class Approve(BaseModel):
    reason: str = ""


class Reject(BaseModel):
    reason: str = ""


class Impersonate(BaseModel):
    user_id: str
    reason: str


@router.get("/academy-types")
def academy_types():
    return service.academy_types()


@router.post("/register", status_code=201)
def register(body: RegistrationRequest, db: Session = Depends(get_db)):
    try:
        org, token = service.register(
            db,
            organisation_name=body.organisation_name,
            slug=body.slug,
            academy_type=body.academy_type,
            admin=body.admin.model_dump(),
            country=body.country,
            accepted_terms=body.accepted_terms,
        )
    except TenancyError as e:
        raise _err(e) from e
    out = org.to_dict(plan="trial")
    if settings.dev_mode:
        out["verification_token"] = token  # never in production; EOS_DEV_MODE=false removes it
    return out


@router.post("/register/verify")
def verify(body: Verify, db: Session = Depends(get_db)):
    """Returns the organisation; status is pending_approval until a super admin approves the package."""
    try:
        return service.verify(db, body.token).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/organisation")
def organisation(
    p: Principal = Depends(require("tenancy:organisation:read", organisation=True)), db: Session = Depends(get_db)
):
    try:
        return service.get_organisation(db, p.organisation_id).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/organisation/entitlement")
def entitlement(
    p: Principal = Depends(require("tenancy:organisation:read", organisation=True)), db: Session = Depends(get_db)
):
    return service.entitlement(db, p.organisation_id)


@router.put("/organisation/modules/{module:path}")
def toggle(
    module: str,
    body: Toggle,
    p: Principal = Depends(require("tenancy:organisation:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.toggle_module(db, p.organisation_id, module, body.enabled)
    except TenancyError as e:
        raise _err(e) from e


@router.put("/organisation/academy-package")
def request_package(
    body: PackageRequest, p: Principal = Depends(require("tenancy:organisation:manage")), db: Session = Depends(get_db)
):
    try:
        return service.request_package(db, p.organisation_id, body.academy_type).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/approve")
def admin_approve(
    org_id: str,
    body: Approve,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    """Approve the organisation's academic package (registration or a requested change)."""
    try:
        return service.approve(db, org_id, approved_by=p.user_id, reason=body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/reject")
def admin_reject(
    org_id: str,
    body: Reject,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    """Reject an organisation's registration awaiting approval."""
    try:
        return service.reject(db, org_id, rejected_by=p.user_id, reason=body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/admin/organisations")
def admin_list(
    status_: str | None = Query(default=None, alias="status"),
    plan: str | None = None,
    academy_type: str | None = None,
    p: Principal = Depends(require("platform:organisations:read")),
    db: Session = Depends(get_db),
):
    return service.list_organisations(db, status=status_, plan=plan, academy_type=academy_type)


@router.get("/admin/organisations/{org_id}")
def admin_get(
    org_id: str, p: Principal = Depends(require("platform:organisations:read")), db: Session = Depends(get_db)
):
    try:
        org = service.get_organisation(db, org_id)
        return {**org.to_dict(), "entitlement": service.entitlement(db, org_id)}
    except TenancyError as e:
        raise _err(e) from e


@router.put("/admin/organisations/{org_id}/status")
def admin_status(
    org_id: str,
    body: StatusChange,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.set_status(db, org_id, body.status, body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.put("/admin/organisations/{org_id}/overrides")
def admin_overrides(
    org_id: str,
    body: Overrides,
    p: Principal = Depends(require("platform:entitlements:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.set_overrides(db, org_id, body.grant_modules, body.revoke_modules, body.reason)
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/impersonate", status_code=201)
def admin_impersonate(
    org_id: str,
    body: Impersonate,
    p: Principal = Depends(require("platform:organisations:impersonate")),
    db: Session = Depends(get_db),
):
    try:
        return service.impersonate(
            db, organisation_id=org_id, user_id=body.user_id, super_admin_id=p.user_id, reason=body.reason
        )
    except TenancyError as e:
        raise _err(e) from e
