"""FastAPI dependencies shared by every router: who is calling, for which organisation, with which permissions.

Every protected route names a key from a contracts/permissions.yaml catalogue through `require(...)`.
`current_principal` alone is authentication (any active user); it is the right guard only for
"who am I" style routes. apps/backend has a test that lists every platform route and checks it is
guarded this way or on its explicit public list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.service import NOT_A_PERSON_ROLES, get_user

MEMBER_ROLE = "member"


@dataclass
class Principal:
    user_id: str
    organisation_id: str | None
    roles: list[str]
    super_admin: bool
    impersonated_by: str | None = None
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def current_principal(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        # Our own HS256 token, or (ADR-0006) a realm's RS256 token that eos_core verified and this service's
        # resolve_oidc_claims mapped to the same shape: `sub` is an identity user id either way.
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    user = get_user(db, claims["sub"])
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user disabled")
    user_id = user.id
    # The lookup above ran in platform scope, and on Postgres `app.bypass_rls=on` is set for the whole
    # transaction it began. End that transaction here (nothing was written), so the request's own queries
    # start a new one carrying the caller's organisation with bypass off: row-level security then applies to
    # the request, not only the Python filters.
    db.rollback()
    # Every principal here is an identity_user row, which is always a person, so a role no person may hold is
    # dropped even if a token carries it: a row written before create_user refused it, or a token minted
    # directly. The roles a person CAN hold are passed through unchanged.
    roles = [r for r in claims.get("roles") or [] if r not in NOT_A_PERSON_ROLES]
    # Every organisation user also holds the implicit `member` role (see platform/tenancy/contracts/permissions.yaml):
    # the grants every member needs to open the shell, such as reading their own organisation and entitlement.
    effective = roles + [MEMBER_ROLE] if claims.get("org") else roles
    p = Principal(
        user_id=user_id,
        organisation_id=claims.get("org"),
        roles=roles,
        super_admin=bool(claims.get("sa")),
        impersonated_by=claims.get("imp"),
        permissions=permissions_for(effective, bool(claims.get("sa"))),
    )
    db.info["organisation_id"] = p.organisation_id  # the request-scoped session carries the tenant
    return p


def require(permission: str, *, organisation: bool = False):
    """Guard a route with a catalogue key. `organisation=True` also insists the caller belongs to an
    organisation, for routes that read or change "own organisation" data."""

    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        if organisation and not p.organisation_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
        return p

    dep.permission = permission  # type: ignore[attr-defined]  # read by the route-coverage test
    return dep


def require_organisation(p: Principal = Depends(current_principal)) -> Principal:
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    return p
