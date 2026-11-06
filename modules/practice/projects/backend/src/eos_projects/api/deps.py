"""Who is calling. A module may not import platform internals (module standard rule 1) and the identity SDK
does not exist yet, so the token is verified here with eos_core: signature and expiry by decode_token,
permissions from every contracts/permissions.yaml by permissions_for. Whether the user is still active is
the gateway's and identity's job; swap this for the identity SDK when it ships."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..application.service import Actor


def current_actor(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    roles = list(claims.get("roles") or [])
    actor = Actor(
        user_id=claims["sub"],
        organisation_id=organisation_id,
        roles=roles,
        permissions=permissions_for(roles, bool(claims.get("sa"))),
    )
    db.info["organisation_id"] = organisation_id  # the request-scoped session carries the tenant
    return actor


def require(*permissions: str):
    """The caller needs at least one of the permissions."""

    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not any(actor.can(p) for p in permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {' or '.join(permissions)}")
        return actor

    return dep


def no_nul(request: Request) -> None:
    """Postgres text cannot hold NUL characters; SQLite can, so tests on SQLite would not show the 500 Postgres gives.
    A NUL in a path id names no row (404); anywhere else in the URL it is an invalid value (422). Request bodies are
    checked by the schemas (Strict)."""
    if any("\x00" in str(v) for v in request.path_params.values()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "not found"})
    if any("\x00" in k or "\x00" in v for k, v in request.query_params.multi_items()):
        message = "query parameters must not contain NUL characters"
        raise HTTPException(422, {"code": "invalid_query", "message": message})
