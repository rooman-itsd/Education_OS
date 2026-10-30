from __future__ import annotations

import hashlib

from eos_core import events
from eos_core.db import scoped
from eos_core.security import create_token, hash_password, verify_password
from eos_core.settings import settings
from eos_core.tenant import get_current_organisation, organisation_scope, platform_scope
from sqlalchemy import func, select, text
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


class PlanLimitReachedError(Exception):
    """The organisation's plan allows no more of something (`limit`: users). Raised before anything is written."""

    def __init__(self, limit: str, allowed: int, used: int):
        super().__init__(f"the plan allows {allowed} {limit}; {used} are active")
        self.limit, self.allowed, self.used = limit, allowed, used


class OrganisationHooks:
    """How identity learns about organisations and plans without importing tenancy or billing (module standard
    rule 1). apps/backend replaces these at startup with tenancy's and billing's implementations."""

    def status(self, db: Session, organisation_id: str) -> str | None:  # noqa: ARG002
        return "active"

    def id_for_slug(self, db: Session, slug: str) -> str | None:  # noqa: ARG002
        return None

    def user_limit(self, db: Session, organisation_id: str) -> int | None:  # noqa: ARG002
        """The plan's ceiling on active users of the organisation; None (the default) is no ceiling."""
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
    if organisation_id is not None:
        limit = hooks.user_limit(db, organisation_id)
        if limit is not None and limit > 0:
            # Count and insert under the organisation's lock, or two requests at limit - 1 would both pass.
            lock_user_seats(db, organisation_id)
            used = count_active_users(db, organisation_id)
            if used >= limit:
                raise PlanLimitReachedError("users", limit, used)
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


# Namespace (first key) of the per-organisation advisory lock that serialises create_user's count-then-insert.
USER_SEATS_LOCK = 0x454F5355  # "EOSU"


def lock_user_seats(db: Session, organisation_id: str) -> None:
    """Hold the organisation's seat lock until the transaction ends (pg_advisory_xact_lock): a second create_user
    for the same organisation waits here, then counts the first one's user. Other organisations are not
    blocked. SQLite (local dev and tests) has one writer at a time and no advisory locks: nothing to do."""
    if db.get_bind().dialect.name != "postgresql":
        return
    key = int.from_bytes(hashlib.sha256(organisation_id.encode("utf-8")).digest()[:4], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:space, :key)"), {"space": USER_SEATS_LOCK, "key": key})


def list_users(db: Session) -> list[User]:
    return list(db.scalars(scoped(db, select(User), User).order_by(User.created_at)))


def count_active_users(db: Session, organisation_id: str) -> int:
    """Active people of one organisation: what the plan's `users` limit counts (billing reads it for usage)."""
    # Filtered by the organisation itself, not only by scoped(): a caller running as the platform (bypass) must
    # still get one organisation's count, never everyone's.
    with organisation_scope(organisation_id):
        q = (
            select(func.count())
            .select_from(User)
            .where(User.organisation_id == organisation_id, User.status == "active")
        )
        return int(db.scalar(q) or 0)


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
        roles=person_roles(user.roles),
        super_admin=user.is_super_admin,
    )
    return user, token


def person_roles(roles: list[str] | None) -> list[str]:
    """The roles a token may carry for a person: a stored row that predates the create_user refusal still lists
    `service`, and feature modules compute permissions from the token's roles claim directly (their api/deps.py
    call eos_core.config.permissions_for on it, never current_principal), so the claim itself must not carry a
    role no person may hold. Used by every token minted for a user (login here, impersonation in tenancy)."""
    return [r for r in (roles or []) if r not in NOT_A_PERSON_ROLES]


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
