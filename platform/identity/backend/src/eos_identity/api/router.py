from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
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
    if any(r in ("super-admin",) for r in body.roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "platform roles are never grantable inside an organisation")
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
    db.commit()
    return user.to_dict()
