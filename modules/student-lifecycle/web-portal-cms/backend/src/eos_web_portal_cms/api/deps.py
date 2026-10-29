"""Who is calling, for which organisation, with which permissions. Identity comes only from a verified bearer
token; permissions come from the contracts' role catalogue (eos_core.config.permissions_for), never from a claim."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.service import Actor

PERM_PAGE_READ = "web-portal-cms:page:read"
PERM_PAGE_MANAGE = "web-portal-cms:page:manage"
PERM_ANNOUNCEMENT_READ = "web-portal-cms:announcement:read"
PERM_ANNOUNCEMENT_MANAGE = "web-portal-cms:announcement:manage"

# Every organisation user also holds the implicit `member` role, as platform/identity grants it
# (platform/tenancy/contracts/permissions.yaml); this module gives it the read keys.
MEMBER_ROLE = "member"


def current_actor(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1].strip())
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    roles = list(claims.get("roles") or [])
    # Pins the request's session to the caller's organisation; on Postgres this drives row-level security.
    db.info["organisation_id"] = organisation_id
    return Actor(
        user_id=claims.get("sub") or "",
        organisation_id=organisation_id,
        roles=roles,
        permissions=permissions_for([*roles, MEMBER_ROLE], bool(claims.get("sa"))),
    )


def require(permission: str):
    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not actor.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        return actor

    dep.permission = permission  # read by the contract drift test
    return dep
