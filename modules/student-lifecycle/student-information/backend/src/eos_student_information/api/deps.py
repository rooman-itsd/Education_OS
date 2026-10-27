"""Authentication and authorization dependencies for student-information.

Derives actor identity and organisation scope strictly from verified JWT bearer tokens.
Uses only approved eos_core interfaces. Never imports platform/identity internals directly.
"""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.service import Actor

PERM_PERSON_READ = "student-information:person:read"
PERM_PERSON_WRITE = "student-information:person:write"
PERM_STATUS_MANAGE = "student-information:status:manage"
PERM_DOCUMENT_MANAGE = "student-information:document:manage"
PERM_ID_CARD_MANAGE = "student-information:id-card:manage"


def current_actor(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Actor:
    """Verifies bearer token, extracts claims, resolves permissions, and sets request tenant context."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc

    organisation_id = claims.get("org")
    if not organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")

    user_id = claims.get("sub") or ""
    roles = list(claims.get("roles") or [])
    is_super_admin = bool(claims.get("sa"))

    permissions = permissions_for(roles, is_super_admin)
    if "perms" in claims and isinstance(claims["perms"], (list, set)):
        permissions = permissions | set(claims["perms"])

    actor = Actor(
        user_id=user_id,
        organisation_id=organisation_id,
        roles=roles,
        permissions=permissions,
    )

    # Scopes the request-level database transaction to the verified organisation
    db.info["organisation_id"] = organisation_id
    return actor


def require(*permissions: str):
    """Enforces that the caller has at least one of the specified permissions."""

    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not any(actor.can(p) for p in permissions):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"requires {' or '.join(permissions)}",
            )
        return actor

    return dep
