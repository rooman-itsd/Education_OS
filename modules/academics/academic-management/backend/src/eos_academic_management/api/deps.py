"""Who is calling, resolved as facility-booking does. A module may not import platform internals (module standard
rule 1) and the identity SDK does not exist yet, so the token is verified here with eos_core: signature and
expiry by decode_token, permission keys from every contracts/permissions.yaml by permissions_for. Swap this for
the identity SDK when it ships.

Which profile roles hold academic-management keys (platform role ids or module role names) is pending on issue
#100; this file maps nothing and grants nothing. The caller's department (HoD scope) is pending too."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.access import PERMISSION_KEYS, Actor
from ..application.errors import forbidden


def current_actor(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Actor:
    """401 without a valid bearer token, 403 without an organisation. The request's session carries the caller's
    organisation, which row-level security reads on Postgres (eos_core.db)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token: no subject")
    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    roles = list(claims.get("roles") or [])
    actor = Actor(
        user_id=user_id,
        organisation_id=organisation_id,
        roles=roles,
        permissions=permissions_for(roles, bool(claims.get("sa"))),
    )
    db.info["organisation_id"] = organisation_id  # the request-scoped session carries the tenant
    return actor


def require(*permissions: str):
    """The caller needs at least one of the permissions: the operation's x-permission in contracts/openapi.yaml.
    A 403 carries the contract's ErrorResponse body. Keys outside contracts/permissions.yaml are a programming
    error, refused when the route is defined."""
    unknown = [p for p in permissions if p not in PERMISSION_KEYS]
    if not permissions or unknown:
        raise ValueError(f"require() needs keys from contracts/permissions.yaml, got {list(permissions)}")

    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not any(actor.can(p) for p in permissions):
            err = forbidden(f"requires {' or '.join(permissions)}")
            raise HTTPException(err.status, err.body())
        return actor

    dep.permissions = frozenset(permissions)  # read by the test that compares each route with its x-permission
    return dep
