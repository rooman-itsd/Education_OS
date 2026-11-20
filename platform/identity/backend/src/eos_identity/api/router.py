from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from ..application import service
from .deps import Principal, current_principal, require

router = APIRouter(tags=["identity"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organisation_slug: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: dict


class CreateUser(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["student"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = service.authenticate(
            db, email=body.email, password=body.password, organisation_slug=body.organisation_slug
        )
    except service.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return {"token": token, "user": user.to_dict()}


class OIDCCallback(BaseModel):
    """What the web shell holds when the provider sends it back: the code from the query string, the PKCE
    verifier it generated, the redirect URI it used and the organisation slug it typed."""

    code: str = Field(min_length=1)
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=40)


@router.get("/auth/oidc/config")
def oidc_config(slug: str = Query(min_length=1, max_length=40), db: Session = Depends(get_db)):
    """ADR-0006: the realm, endpoints, client id and PKCE parameters for "Continue with your institution".
    Public and secret-free. 404 when the organisation has no realm, so the shell shows no button."""
    cfg = service.oidc_config(db, slug)
    if cfg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not configured for this organisation")
    return cfg


@router.post("/auth/oidc/callback", response_model=LoginResponse)
def oidc_callback(body: OIDCCallback, db: Session = Depends(get_db)):
    """Finish the authorization code flow and answer like /auth/login: the platform's own token. A person the
    provider knows but identity does not gets 403 `no_account` (ADR-0006 decision 4)."""
    try:
        user, token = service.authenticate_oidc(
            db, slug=body.slug, code=body.code, code_verifier=body.code_verifier, redirect_uri=body.redirect_uri
        )
    except service.OIDCNotConfiguredError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.NoAccountError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_account") from e
    except service.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return {"token": token, "user": user.to_dict()}


@router.get("/auth/me")
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = service.get_user(db, p.user_id)
    return {**user.to_dict(), "permissions": sorted(p.permissions), "impersonated_by": p.impersonated_by}


@router.get("/users")
def list_users(p: Principal = Depends(require("identity:user:read", organisation=True)), db: Session = Depends(get_db)):
    return [u.to_dict() for u in service.list_users(db)]


@router.post("/users", status_code=201)
def create_user(
    body: CreateUser,
    p: Principal = Depends(require("identity:user:manage", organisation=True)),
    db: Session = Depends(get_db),
):
    _refuse_platform_roles(body.roles)
    try:
        user = service.create_user(
            db,
            organisation_id=p.organisation_id,
            email=body.email,
            name=body.name,
            password=body.password,
            roles=body.roles,
        )
    except service.RoleNotAssignableError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except service.PlanLimitReachedError as e:
        return _plan_limit(e)
    db.commit()
    return user.to_dict()


PLATFORM_ROLES = frozenset({"super-admin"})


def _refuse_platform_roles(roles: list[str]) -> None:
    if PLATFORM_ROLES.intersection(roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "platform roles are never grantable inside an organisation")


def _plan_limit(e: service.PlanLimitReachedError) -> JSONResponse:
    # the same shape as the entitlement gate's refusals: `code` beside `detail`
    return JSONResponse(
        {"detail": str(e), "code": "plan_limit_reached", "limit": e.limit, "allowed": e.allowed, "used": e.used},
        status_code=status.HTTP_409_CONFLICT,
    )


def _conflict(code: str, e: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(e), "code": code}, status_code=status.HTTP_409_CONFLICT)


UserId = Path(min_length=1, max_length=36)


class UpdateUser(BaseModel):
    """Any of name, email and roles; a field left out stays as it is."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    roles: list[str] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _something(self):
        if self.name is None and self.email is None and self.roles is None:
            raise ValueError("give at least one of name, email and roles")
        return self


@router.patch("/users/{user_id}")
def update_user(
    body: UpdateUser,
    user_id: str = UserId,
    p: Principal = Depends(require("identity:user:manage", organisation=True)),
    db: Session = Depends(get_db),
):
    """DPDP s.12 correction, and role changes, inside the caller's organisation."""
    if body.roles is not None:
        _refuse_platform_roles(body.roles)
    try:
        user = service.update_user(
            db,
            organisation_id=p.organisation_id,
            user_id=user_id,
            actor=p.user_id,
            name=body.name,
            email=body.email,
            roles=body.roles,
        )
    except service.UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.RoleNotAssignableError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except service.EmailTakenError as e:
        return _conflict("email_taken", e)
    except service.LastAdminError as e:
        return _conflict("last_admin", e)
    except service.PlanLimitReachedError as e:
        return _plan_limit(e)
    db.commit()
    return user.to_dict()


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: str = UserId,
    p: Principal = Depends(require("identity:user:manage", organisation=True)),
    db: Session = Depends(get_db),
):
    """Offboarding: the user can no longer sign in, and platform routes refuse their tokens from the next request."""
    try:
        user = service.disable_user(db, organisation_id=p.organisation_id, user_id=user_id, actor=p.user_id)
    except service.UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.LastAdminError as e:
        return _conflict("last_admin", e)
    db.commit()
    return user.to_dict()


@router.post("/users/{user_id}/enable")
def enable_user(
    user_id: str = UserId,
    p: Principal = Depends(require("identity:user:manage", organisation=True)),
    db: Session = Depends(get_db),
):
    try:
        user = service.enable_user(db, organisation_id=p.organisation_id, user_id=user_id, actor=p.user_id)
    except service.UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.PlanLimitReachedError as e:
        return _plan_limit(e)
    db.commit()
    return user.to_dict()


@router.delete("/users/{user_id}", status_code=204)
def erase_user(
    user_id: str = UserId,
    p: Principal = Depends(require("identity:user:erase", organisation=True)),
    db: Session = Depends(get_db),
):
    """DPDP s.12(3) erasure: the row becomes a tombstone (other modules hold the id) and identity.user.erased asks
    each module to erase what it holds."""
    try:
        service.erase_user(db, organisation_id=p.organisation_id, user_id=user_id, actor=p.user_id)
    except service.UserNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.LastAdminError as e:
        return _conflict("last_admin", e)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
