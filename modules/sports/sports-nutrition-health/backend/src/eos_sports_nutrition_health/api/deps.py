"""Who is calling. A module may not import platform internals (module standard rule 1) and the identity SDK
does not exist yet, so the token is verified here with eos_core: signature and expiry by decode_token,
permissions from every contracts/permissions.yaml by permissions_for. Swap this for the identity SDK when it ships."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.service import ATHLETE_ROLES, MODULE, Actor


def _self_only(roles: list[str]) -> bool:
    """True when every sports-nutrition-health permission the caller has comes from an athlete role."""
    if not ATHLETE_ROLES & set(roles):
        return False
    others = permissions_for([r for r in roles if r not in ATHLETE_ROLES])
    return not any(p.startswith(f"{MODULE}:") for p in others)


def current_actor(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"code": "unauthorised", "message": "missing bearer token"})
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, {"code": "unauthorised", "message": f"invalid token: {e}"}
        ) from e
    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, {"code": "forbidden", "message": "this endpoint needs an organisation user"}
        )
    roles = list(claims.get("roles") or [])
    actor = Actor(
        user_id=claims["sub"],
        organisation_id=organisation_id,
        roles=roles,
        permissions=permissions_for(roles, bool(claims.get("sa"))),
        self_only=_self_only(roles),
    )
    db.info["organisation_id"] = organisation_id  # the request-scoped session carries the tenant
    return actor


def require(permission: str):
    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not actor.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "forbidden", "message": f"requires {permission}"})
        return actor

    return dep
