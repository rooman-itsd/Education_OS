"""Who is calling. A module may not import platform internals (module standard rule 1) and the identity SDK does not
exist yet, so the token is verified here with eos_core, as hostel and facility-booking do: signature and expiry by
decode_token, permission keys from every contracts/permissions.yaml by permissions_for. Swap this for the identity SDK
when it ships."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.access import Actor


def current_actor(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"code": "unauthenticated", "message": "missing token"})
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, {"code": "unauthenticated", "message": "invalid token"}
        ) from e
    if not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"code": "unauthenticated", "message": "token has no user"})
    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "forbidden", "message": "needs an organisation user"})
    roles = list(claims.get("roles") or [])
    db.info["organisation_id"] = organisation_id  # the request-scoped session carries the tenant
    return Actor(
        user_id=claims["sub"],
        organisation_id=organisation_id,
        permissions=permissions_for(roles, bool(claims.get("sa"))),
    )


def require(*permissions: str):
    """The caller needs at least one of the permissions the contract names for the operation."""

    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not any(actor.can(p) for p in permissions):
            message = f"requires {' or '.join(permissions)}"
            raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "forbidden", "message": message})
        return actor

    return dep
