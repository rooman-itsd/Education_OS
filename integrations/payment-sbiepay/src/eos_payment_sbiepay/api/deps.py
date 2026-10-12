"""Who is calling and with which permissions. An integration may import only eos_core, eos_sdk and
eos_testing (tools/scripts/check-boundaries.py), so this reads the platform token through eos_core rather
than eos_identity. Replace with the SDK's dependency once packages/sdk provides one."""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session


@dataclass
class Principal:
    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def current_principal(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    if not claims.get("org"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    roles = list(claims.get("roles") or [])
    p = Principal(
        user_id=claims["sub"],
        organisation_id=claims["org"],
        roles=roles,
        permissions=permissions_for(roles, bool(claims.get("sa"))),
    )
    db.info["organisation_id"] = p.organisation_id  # the request-scoped session carries the tenant
    return p


def require(permission: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        return p

    return dep
