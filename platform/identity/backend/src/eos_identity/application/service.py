from __future__ import annotations

import hashlib

import jwt
from eos_core import events, oidc
from eos_core.config import expand_roles
from eos_core.db import SessionLocal, scoped, utcnow
from eos_core.security import create_token, hash_password, verify_password
from eos_core.settings import settings
from eos_core.tenant import get_current_organisation, organisation_scope, platform_scope
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..domain.models import User


class AuthError(Exception):
    pass


class NoAccountError(AuthError):
    """A verified realm identity that no user of the organisation carries (ADR-0006 decision 4: Keycloak
    authenticates, identity decides who has an account)."""


class OIDCNotConfiguredError(AuthError):
    """The slug has no realm, or OIDC is off on this API."""


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
    if organisation_id is not None and not is_learner(roles):
        # The plan's `users` limit is on staff accounts; learners are the plan's `students`, never refused here.
        limit = hooks.user_limit(db, organisation_id)
        if limit is not None and limit > 0:
            # Count and insert under the organisation's lock, or two requests at limit - 1 would both pass.
            lock_user_seats(db, organisation_id)
            used = count_staff_users(db, organisation_id)
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
    """The organisation's users, without erased ones: a tombstone is kept for the ids other modules hold, not to be
    managed."""
    q = scoped(db, select(User), User).where(User.status != ERASED)
    return list(db.scalars(q.order_by(User.created_at)))


# The roles of the people an organisation teaches, not employs. A role is a learner's when it is one of these or
# its dashboard layout extends one, directly or through another (platform/identity/config/dashboards/*.yaml,
# e.g. law-student extends student), as eos_core.config.expand_roles follows it.
LEARNER_ROLES = frozenset({"student", "applicant"})


def is_learner(roles: list[str] | None) -> bool:
    """Whether a person with these roles is a learner (a student or an applicant): any of the roles is, or
    extends, one of LEARNER_ROLES. Learners count against the plan's `students` limit, never its `users`."""
    return bool(LEARNER_ROLES.intersection(expand_roles(list(roles or []))))


def count_staff_users(db: Session, organisation_id: str) -> int:
    """Active staff accounts of one organisation: what the plan's `users` limit counts (billing reads it for
    usage). Learners (`is_learner`) are left out; they are the plan's `students`."""
    # Filtered by the organisation itself, not only by scoped(): a caller running as the platform (bypass) must
    # still get one organisation's count, never everyone's. Roles are a JSON list, so they are read and the
    # learners told apart here, where the role tree is known.
    with organisation_scope(organisation_id):
        q = select(User.roles).where(User.organisation_id == organisation_id, User.status == "active")
        return sum(1 for roles in db.scalars(q) if not is_learner(roles))


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


# ---- OpenID Connect (ADR-0006) -------------------------------------------------------------------------


def oidc_config(db: Session, slug: str) -> dict | None:
    """What the web shell needs to start the authorization code flow for `slug`, or None when the organisation
    has no realm (EOS_OIDC_REALMS), does not exist or is not active. Public: it holds no secret."""
    if not oidc.realm_exists(slug):
        return None
    org_id = hooks.id_for_slug(db, slug)
    if not org_id or hooks.status(db, org_id) != "active":
        return None
    return oidc.endpoints(slug)


def user_for_oidc_claims(db: Session, claims: dict) -> User:
    """The user a verified realm token names: by (organisation of the realm, `oidc_subject`); on first sight by
    the token's verified email, which links the subject to that user. The super admin has no organisation and
    is never matched. Raises NoAccountError when nobody matches, AuthError when the organisation or the user is
    not active."""
    realm, subject = claims.get("realm"), claims.get("sub")
    if not realm or not subject:
        raise AuthError("token names no realm subject")
    org_id = hooks.id_for_slug(db, realm)
    if not org_id:
        raise AuthError("unknown organisation")
    status = hooks.status(db, org_id)
    if status != "active":
        raise AuthError(f"organisation is {status or 'missing'}")
    with platform_scope():
        user = db.scalar(select(User).where(User.organisation_id == org_id, User.oidc_subject == subject))
        if user is None:
            email = claims.get("email")
            if email and claims.get("email_verified") is True:
                user = db.scalar(
                    select(User).where(
                        User.organisation_id == org_id,
                        User.email == email.lower(),
                        User.oidc_subject.is_(None),
                        User.status == "active",
                    )
                )
                if user is not None:
                    user.oidc_subject = subject
                    events.publish(db, "identity.user.oidc_linked", org_id, {"user_id": user.id, "realm": realm})
                    db.commit()
    if user is None:
        raise NoAccountError("no_account")
    if user.status != "active":
        raise AuthError("user disabled")
    return user


def platform_claims(user: User, claims: dict) -> dict:
    """The platform's own claim shape for a user a realm token names, so `current_principal` and the module
    dependencies read it like one of our tokens. `sa` is always false: the super admin never uses OIDC."""
    return {
        "sub": user.id,
        "org": user.organisation_id,
        "roles": person_roles(user.roles),
        "sa": False,
        "iat": claims.get("iat"),
        "exp": claims.get("exp"),
        "oidc": {"realm": claims.get("realm"), "sub": claims.get("sub")},
    }


def resolve_oidc_claims(claims: dict) -> dict:
    """eos_core.oidc.hooks.resolve_claims: apps/backend registers this at startup. Opens its own session
    because the call comes from inside decode_token, which has none; refusals become OIDCError so the
    caller's `except jwt.PyJWTError` answers 401."""
    db = SessionLocal()
    try:
        try:
            user = user_for_oidc_claims(db, claims)
        except AuthError as e:
            raise oidc.OIDCError(str(e)) from e
        return platform_claims(user, claims)
    finally:
        db.close()


def authenticate_oidc(db: Session, *, slug: str, code: str, code_verifier: str, redirect_uri: str) -> tuple[User, str]:
    """Finish the authorization code flow the web shell started: redeem the code at the realm's token endpoint,
    verify the id token against the realm's keys, map it to a user, and issue the platform's own token exactly as
    the password login does, so nothing else in the API changes."""
    if oidc_config(db, slug) is None:
        raise OIDCNotConfiguredError("OIDC is not configured for this organisation")
    try:
        tokens = oidc.exchange_code(slug, code=code, code_verifier=code_verifier, redirect_uri=redirect_uri)
        id_token = tokens.get("id_token") if isinstance(tokens, dict) else None
        if not id_token:
            raise AuthError("the realm returned no id token")
        claims = oidc.verify_realm_token(id_token, token_type=oidc.ID_TOKEN)
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid id token: {e}") from e
    if claims.get("realm") != slug:
        raise AuthError("id token belongs to another realm")
    user = user_for_oidc_claims(db, claims)
    token = create_token(
        user_id=user.id,
        organisation_id=user.organisation_id,
        roles=person_roles(user.roles),
        super_admin=False,
    )
    return user, token


# ---- Updating, disabling and erasing users (DPDP s.12 correction and erasure; offboarding) -------------------

ACTIVE, DISABLED, ERASED = "active", "disabled", "erased"
ADMIN_ROLE = "org-admin"
ERASED_NAME = "Erased user"
# A tombstone address: unique per user (the organisation's email constraint), and under the `.invalid` top-level
# domain (RFC 2606), so it can never belong to anyone or receive mail.
ERASED_EMAIL_DOMAIN = "erased.invalid"
# Not a hash verify_password can ever match (it needs four `$`-separated parts), so nobody signs in with it.
NO_PASSWORD = "!erased"


class UserNotFoundError(Exception):
    """No such user in the organisation: another organisation's user, an unknown id, or an erased user."""


class EmailTakenError(Exception):
    """Another user of the organisation already has the email."""


class LastAdminError(Exception):
    """The change would leave the organisation without an active admin."""


def is_admin(roles: list[str] | None) -> bool:
    """Whether a person with these roles is an organisation admin: `org-admin`, held or inherited."""
    return ADMIN_ROLE in expand_roles(list(roles or []))


def _manageable(db: Session, organisation_id: str, user_id: str) -> User:
    """The organisation's user `user_id`, never another organisation's (filtered by the organisation itself, as
    well as by the session's scope and, on Postgres, row-level security) and never an erased one."""
    with organisation_scope(organisation_id):
        q = select(User).where(User.id == user_id, User.organisation_id == organisation_id)
        user = db.scalar(scoped(db, q, User))
    if user is None or user.status == ERASED:
        raise UserNotFoundError("user not found")
    return user


def _guard_last_admin(db: Session, user: User, *, stays_admin: bool) -> None:
    """Refuse a change that takes the last active admin away from the organisation: disabling or erasing them, or
    taking `org-admin` from their roles. Under the organisation's seat lock, so two admins disabling each other
    at the same moment cannot both pass on Postgres."""
    if stays_admin or user.status != ACTIVE or not is_admin(user.roles):
        return
    lock_user_seats(db, user.organisation_id)
    with organisation_scope(user.organisation_id):
        q = select(User.roles).where(
            User.organisation_id == user.organisation_id, User.status == ACTIVE, User.id != user.id
        )
        others = sum(1 for roles in db.scalars(q) if is_admin(roles))
    if others == 0:
        raise LastAdminError("the organisation's last active admin cannot be disabled, erased or lose org-admin")


def _guard_staff_seat(db: Session, organisation_id: str) -> None:
    """The plan's `users` limit for one more active staff account, as create_user applies it."""
    limit = hooks.user_limit(db, organisation_id)
    if limit is not None and limit > 0:
        lock_user_seats(db, organisation_id)
        used = count_staff_users(db, organisation_id)
        if used >= limit:
            raise PlanLimitReachedError("users", limit, used)


def update_user(
    db: Session,
    *,
    organisation_id: str,
    user_id: str,
    actor: str | None,
    name: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
) -> User:
    """Correct a user's name or email, or change their roles (None: leave as is). Roles follow create_user's rules:
    no role a person may not hold, and a learner who becomes staff while active must fit the plan's `users` limit.
    Publishes identity.user.updated naming the changed fields, never their values: the audit record is permanent.
    Refusals raise before anything is written."""
    if roles is not None:
        refused = NOT_A_PERSON_ROLES.intersection(roles)
        if refused:
            raise RoleNotAssignableError(f"{', '.join(sorted(refused))} is not a role a person can hold")
    user = _manageable(db, organisation_id, user_id)
    changed: list[str] = []
    if name is not None and name != user.name:
        changed.append("name")
    if email is not None and email.lower() != user.email:
        with organisation_scope(organisation_id):
            q = select(User.id).where(User.organisation_id == organisation_id, User.email == email.lower())
            if db.scalar(q) is not None:
                raise EmailTakenError("another user of the organisation has this email")
        changed.append("email")
    if roles is not None and list(roles) != list(user.roles or []):
        _guard_last_admin(db, user, stays_admin=is_admin(roles))
        if user.status == ACTIVE and is_learner(user.roles) and not is_learner(roles):
            _guard_staff_seat(db, organisation_id)
        changed.append("roles")
    if not changed:
        return user
    if "name" in changed:
        user.name = name
    if "email" in changed:
        user.email = email.lower()
    payload: dict = {"user_id": user.id, "changed": changed}
    if "roles" in changed:
        user.roles = list(roles)
        payload["roles"] = list(roles)
    db.flush()
    events.publish(db, "identity.user.updated", organisation_id, payload, actor=actor)
    return user


def disable_user(db: Session, *, organisation_id: str, user_id: str, actor: str | None) -> User:
    """Stop the user signing in: login and the Keycloak paths take active users only, and current_principal
    refuses the user's existing tokens on every platform route from the next request. The user stops counting
    against the plan's `users` limit (count_staff_users counts active users). Already disabled: nothing changes."""
    user = _manageable(db, organisation_id, user_id)
    if user.status == DISABLED:
        return user
    _guard_last_admin(db, user, stays_admin=False)
    user.status = DISABLED
    db.flush()
    events.publish(db, "identity.user.disabled", organisation_id, {"user_id": user.id}, actor=actor)
    return user


def enable_user(db: Session, *, organisation_id: str, user_id: str, actor: str | None) -> User:
    """Let a disabled user sign in again. A staff user takes a seat again, so the plan's `users` limit applies.
    An erased user cannot come back (UserNotFoundError). Already active: nothing changes."""
    user = _manageable(db, organisation_id, user_id)
    if user.status == ACTIVE:
        return user
    if not is_learner(user.roles):
        _guard_staff_seat(db, organisation_id)
    user.status = ACTIVE
    db.flush()
    events.publish(db, "identity.user.enabled", organisation_id, {"user_id": user.id}, actor=actor)
    return user


def erase_user(db: Session, *, organisation_id: str, user_id: str, actor: str | None) -> User | None:
    """Erase a user (DPDP s.12(3)) by anonymising the row, not deleting it: other modules and the audit trail hold
    the id, and a deleted row would leave them pointing at nothing. The name and email become a tombstone, the
    password hash and the Keycloak subject are removed, the roles are cleared and the status is `erased`, which no
    sign-in path and no token check accepts. identity.user.erased asks every module to erase or anonymise what it
    holds for the id. Returns None, and publishes nothing, when the user was already erased."""
    with organisation_scope(organisation_id):
        q = select(User).where(User.id == user_id, User.organisation_id == organisation_id)
        user = db.scalar(scoped(db, q, User))
    if user is None:
        raise UserNotFoundError("user not found")
    if user.status == ERASED:
        return None
    _guard_last_admin(db, user, stays_admin=False)
    user.name = ERASED_NAME
    user.email = f"erased-{user.id}@{ERASED_EMAIL_DOMAIN}"
    user.password_hash = NO_PASSWORD
    user.oidc_subject = None
    user.roles = []
    user.status = ERASED
    db.flush()
    erased_at = utcnow().isoformat()
    events.publish(
        db, "identity.user.erased", organisation_id, {"user_id": user.id, "erased_at": erased_at}, actor=actor
    )
    return user
