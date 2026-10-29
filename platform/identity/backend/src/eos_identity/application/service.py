from __future__ import annotations

from eos_core import events
from eos_core.db import scoped
from eos_core.security import create_token, hash_password, verify_password
from eos_core.settings import settings
from eos_core.tenant import get_current_organisation, platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import User


class AuthError(Exception):
    pass


# Roles that name something other than a person. identity_user holds people only (domain/models.py: "A person who
# can sign in"), so no user may carry one. `service` exists so notification:message:send has a holder in the
# catalogue; the modules that send do it in-process through notification's application service, with no
# principal at all, so no person ever needs it. Refused here, where every role assignment passes (the users
# route, organisation registration in tenancy, the super-admin seed), and ignored again in current_principal
# for any token or row that predates this check.
NOT_A_PERSON_ROLES = frozenset({"service"})


class RoleNotAssignableError(Exception):
    """A role no person may hold. Raised before anything is written."""


class OrganisationHooks:
    """How identity learns about organisations without importing tenancy (module standard rule 1).
    apps/backend replaces these at startup with tenancy's implementations."""

    def status(self, db: Session, organisation_id: str) -> str | None:  # noqa: ARG002
        return "active"

    def id_for_slug(self, db: Session, slug: str) -> str | None:  # noqa: ARG002
        return None


hooks = OrganisationHooks()


def create_user(
    db: Session,
    *,
    organisation_id: str | None,
    email: str,
    name: str,
    password: str,
    roles: list[str],
    is_super_admin: bool = False,
) -> User:
    refused = NOT_A_PERSON_ROLES.intersection(roles or [])
    if refused:
        raise RoleNotAssignableError(f"{', '.join(sorted(refused))} is not a role a person can hold")
    user = User(
        organisation_id=organisation_id,
        email=email.lower(),
        name=name,
        password_hash=hash_password(password),
        roles=roles,
        is_super_admin=is_super_admin,
    )
    db.add(user)
    db.flush()
    events.publish(db, "identity.user.created", organisation_id, {"user_id": user.id, "roles": roles})
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(scoped(db, select(User), User).order_by(User.created_at)))


def get_user(db: Session, user_id: str) -> User | None:
    with platform_scope():
        return db.get(User, user_id)


def authenticate(db: Session, *, email: str, password: str, organisation_slug: str | None) -> tuple[User, str]:
    """Pre-auth lookup runs in platform scope (no organisation known yet); the result is one user."""
    with platform_scope():
        q = select(User).where(User.email == email.lower(), User.status == "active")
        if organisation_slug:
            org_id = hooks.id_for_slug(db, organisation_slug)
            if not org_id:
                raise AuthError("unknown organisation")
            q = q.where(User.organisation_id == org_id)
        users = list(db.scalars(q))
    if len(users) > 1:
        raise AuthError("email exists in more than one organisation; pass organisation_slug")
    if not users or not verify_password(password, users[0].password_hash):
        raise AuthError("invalid credentials")
    user = users[0]
    if user.organisation_id:
        status = hooks.status(db, user.organisation_id)
        if status != "active":
            raise AuthError(f"organisation is {status or 'missing'}")
    token = create_token(
        user_id=user.id,
        organisation_id=user.organisation_id,
        roles=list(user.roles or []),
        super_admin=user.is_super_admin,
    )
    return user, token


def seed_super_admin(db: Session) -> None:
    if not settings.super_admin_email or not settings.super_admin_password:
        return
    with platform_scope():
        exists = db.scalar(
            select(User).where(User.email == settings.super_admin_email.lower(), User.is_super_admin.is_(True))
        )
        if exists:
            return
        create_user(
            db,
            organisation_id=None,
            email=settings.super_admin_email,
            name="Super Admin",
            password=settings.super_admin_password,
            roles=["super-admin"],
            is_super_admin=True,
        )
        db.commit()


def current_org_or_none() -> str | None:
    return get_current_organisation()
