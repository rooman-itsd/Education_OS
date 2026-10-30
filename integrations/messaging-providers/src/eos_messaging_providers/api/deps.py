"""Who is calling and with which permissions. An integration may import only eos_core, eos_sdk and eos_testing
(tools/scripts/check-boundaries.py), so this reads the platform token through eos_core rather than eos_identity,
as integrations/payment-sbiepay does. Replace both with the SDK's dependency once packages/sdk provides one.

Unlike payment-sbiepay's, this does not insist on an organisation. Provider credentials are platform-level, so the
callers here are a super admin and platform support, and neither belongs to one. Like payment-sbiepay's, it reads
the token without looking the user up, so a disabled user's token keeps working until it expires.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from eos_core.config import permissions_for
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status


@dataclass
class Principal:
    user_id: str
    organisation_id: str | None = None
    roles: list[str] = field(default_factory=list)
    super_admin: bool = False
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    if not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token: no subject")
    roles = list(claims.get("roles") or [])
    super_admin = bool(claims.get("sa"))
    return Principal(
        user_id=claims["sub"],
        organisation_id=claims.get("org"),
        roles=roles,
        super_admin=super_admin,
        permissions=permissions_for(roles, super_admin),
    )


def require(permission: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        return p

    dep.permission = permission  # type: ignore[attr-defined]  # read by the host's route-coverage test once mounted
    return dep
