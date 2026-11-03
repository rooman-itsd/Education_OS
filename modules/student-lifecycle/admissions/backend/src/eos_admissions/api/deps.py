"""Who is calling, for which organisation, with which permissions. Identity comes only from a verified bearer
token; permissions come from the contracts' role catalogue (eos_core.config.permissions_for), never from a claim."""

from __future__ import annotations

import jwt
from eos_core.config import permissions_for
from eos_core.db import get_db
from eos_core.security import decode_token
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..application.service import Actor

PERM_APPLICATION_READ = "admissions:application:read"
PERM_APPLICATION_MANAGE = "admissions:application:manage"
PERM_DOCUMENT_VERIFY = "admissions:document:verify"
PERM_MERIT_LIST_MANAGE = "admissions:merit-list:manage"
PERM_OFFER_MANAGE = "admissions:offer:manage"
PERM_REPORT_READ = "admissions:report:read"
PERM_SELF_READ = "admissions:self:read"


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
        permissions=permissions_for(roles, bool(claims.get("sa"))),
    )


def public_organisation(org_slug: str, request: Request, db: Session = Depends(get_db)) -> str:
    """The organisation for an anonymous /public/{org_slug}/ request. The host gateway resolves the slug, checks the
    organisation is active and entitled to admissions, and leaves its id in request.state; this module cannot look
    slugs up itself (that is platform/tenancy's data). No id means the slug did not resolve: 404, never a guess."""
    organisation_id = getattr(request.state, "organisation_id", None)
    if not organisation_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "unknown_organisation", "message": f"no organisation {org_slug!r} accepts applications here"},
        )
    db.info["organisation_id"] = organisation_id
    return organisation_id


def require(permission: str):
    def dep(actor: Actor = Depends(current_actor)) -> Actor:
        if not actor.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {permission}")
        return actor

    dep.permission = permission  # read by the contract drift test
    return dep
