from __future__ import annotations

import re
import secrets
from datetime import timedelta

from eos_billing.application import service as billing
from eos_core import events, notify
from eos_core.config import load_profiles
from eos_core.db import scoped, utcnow
from eos_core.entitlement import compute_entitlement
from eos_core.security import create_token
from eos_core.settings import settings
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application import service as identity
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import Organisation, OrganisationModule, RegistrationToken

AUTO_APPROVE = settings.auto_approve  # module-level so tests can flip it
SLUG_RE = re.compile(r"^[a-z0-9-]{3,40}$")
RESERVED = {"admin", "api", "www", "app", "platform"}


class TenancyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def academy_types() -> list[dict]:
    return [
        {
            "id": p["profile"],
            "title": p["title"],
            "description": p.get("description", ""),
            "specialized_suites": p["suites"].get("specialized", []),
        }
        for p in load_profiles().values()
    ]


def register(
    db: Session,
    *,
    organisation_name: str,
    slug: str,
    academy_type: str,
    admin: dict,
    country: str | None = None,
    accepted_terms: bool = False,
) -> tuple[Organisation, str]:
    if not settings.registration_open:
        raise TenancyError("registration is closed", 403)
    if not accepted_terms:
        raise TenancyError("terms must be accepted")
    if not SLUG_RE.match(slug) or slug in RESERVED:
        raise TenancyError("slug must be 3-40 chars of a-z, 0-9, - and not reserved")
    if academy_type not in load_profiles():
        raise TenancyError(f"unknown academy type {academy_type}")
    with platform_scope():
        if db.scalar(select(Organisation).where(Organisation.slug == slug)):
            raise TenancyError("slug already in use", 409)
    org = Organisation(name=organisation_name, slug=slug, academy_type=academy_type, country=country)
    db.add(org)
    db.flush()
    with organisation_scope(org.id):
        identity.create_user(
            db,
            organisation_id=org.id,
            email=admin["email"],
            name=admin["name"],
            password=admin["password"],
            roles=["org-admin"],
        )
        token = secrets.token_urlsafe(32)
        db.add(
            RegistrationToken(
                organisation_id=org.id,
                token=token,
                email=admin["email"].lower(),
                expires_at=utcnow() + timedelta(hours=48),
            )
        )
        billing.start_trial(db, organisation_id=org.id)
        events.publish(
            db,
            "tenancy.organisation.registered",
            org.id,
            {"organisation_id": org.id, "slug": slug, "academy_type": academy_type, "admin_email": admin["email"]},
        )
    notify.send_email(
        admin["email"],
        "Verify your Education OS organisation",
        f"Welcome to {organisation_name}. Verify with token {token}",
        token=token,
        organisation_id=org.id,
    )
    db.commit()
    return org, token


def verify(db: Session, token: str) -> Organisation:
    with platform_scope():
        rt = db.scalar(select(RegistrationToken).where(RegistrationToken.token == token))
        if not rt or rt.used or rt.expires_at.replace(tzinfo=None) < utcnow().replace(tzinfo=None):
            raise TenancyError("invalid or expired token", 400)
        org = db.get(Organisation, rt.organisation_id)
        rt.used = True
        events.publish(
            db, "tenancy.organisation.verified", org.id, {"organisation_id": org.id, "academy_type": org.academy_type}
        )
        if AUTO_APPROVE:
            _activate(db, org, approved_by=None, reason="auto-approved")
        else:
            org.status = "pending_approval"
            events.publish(
                db,
                "tenancy.package.requested",
                org.id,
                {"organisation_id": org.id, "academy_type": org.academy_type, "kind": "registration"},
            )
        db.commit()
        return org


def _admin_email(db: Session, organisation_id: str) -> str | None:
    with platform_scope():
        email = db.scalar(
            select(RegistrationToken.email)
            .where(RegistrationToken.organisation_id == organisation_id)
            .order_by(RegistrationToken.expires_at.desc())
        )
        if email:
            return email
        try:
            from eos_identity.domain.models import User

            return db.scalar(
                select(User.email).where(User.organisation_id == organisation_id).order_by(User.created_at.asc())
            )
        except Exception:
            return None


def _activate(db: Session, org: Organisation, *, approved_by: str | None, reason: str) -> None:
    org.status, org.status_reason = "active", reason
    events.publish(
        db,
        "tenancy.organisation.approved",
        org.id,
        {"organisation_id": org.id, "academy_type": org.academy_type, "approved_by": approved_by},
        actor=approved_by,
    )
    events.publish(db, "tenancy.organisation.activated", org.id, {"organisation_id": org.id})
    email = _admin_email(db, org.id)
    if email:
        notify.send_email(
            email,
            f"Your Education OS organisation {org.name} has been approved",
            f"Congratulations! Your organisation {org.name} has been approved on the {org.academy_type} package. You can now sign in to your administrator dashboard.",
            organisation_id=org.id,
            academy_type=org.academy_type,
            status="active",
        )


def approve(db: Session, organisation_id: str, *, approved_by: str, reason: str = "") -> Organisation:
    """Super admin approves the academic package: at registration, or a requested package change."""
    org = get_organisation(db, organisation_id)
    with platform_scope():
        if org.requested_academy_type:
            previous = org.academy_type
            org.academy_type, org.requested_academy_type = org.requested_academy_type, None
            events.publish(
                db,
                "tenancy.package.changed",
                org.id,
                {"organisation_id": org.id, "from": previous, "to": org.academy_type, "approved_by": approved_by},
                actor=approved_by,
            )
            _changed(db, org.id)
            email = _admin_email(db, org.id)
            if email:
                notify.send_email(
                    email,
                    f"Academic package approved for {org.name}",
                    f"Your request to change academic package to {org.academy_type} has been approved.",
                    organisation_id=org.id,
                    academy_type=org.academy_type,
                )
            if org.status == "active":
                db.commit()
                return org
        if org.status != "pending_approval":
            raise TenancyError(f"organisation is {org.status}, nothing to approve", 409)
        _activate(db, org, approved_by=approved_by, reason=reason or "approved")
        db.commit()
    return org


def request_package(db: Session, organisation_id: str, academy_type: str) -> Organisation:
    """An organisation asks to switch academic package. Takes effect only when a super admin approves."""
    if academy_type not in load_profiles():
        raise TenancyError(f"unknown academy type {academy_type}")
    org = get_organisation(db, organisation_id)
    if academy_type == org.academy_type:
        raise TenancyError("already on this academic package", 409)
    with platform_scope():
        org.requested_academy_type = academy_type
        events.publish(
            db,
            "tenancy.package.requested",
            org.id,
            {"organisation_id": org.id, "academy_type": academy_type, "kind": "change"},
        )
        db.commit()
    return org


def organisation_status(db: Session, organisation_id: str) -> str | None:
    with platform_scope():
        org = db.get(Organisation, organisation_id)
    return org.status if org else None


def organisation_id_for_slug(db: Session, slug: str) -> str | None:
    with platform_scope():
        org = db.scalar(select(Organisation).where(Organisation.slug == slug))
    return org.id if org else None


def get_organisation(db: Session, organisation_id: str) -> Organisation:
    with platform_scope():
        org = db.get(Organisation, organisation_id)
    if not org:
        raise TenancyError("organisation not found", 404)
    return org


def entitlement(db: Session, organisation_id: str) -> dict:
    org = get_organisation(db, organisation_id)
    profile = load_profiles()[org.academy_type]
    plan = billing.current_plan(db, organisation_id)
    with organisation_scope(organisation_id):
        rows = list(db.scalars(scoped(db, select(OrganisationModule), OrganisationModule)))
    overrides = [r.module for r in rows if r.override and r.enabled]
    disabled = [r.module for r in rows if not r.enabled]
    ent = compute_entitlement(profile, plan, overrides=overrides, disabled=disabled)
    sub = billing.get_subscription(db, organisation_id)
    return {
        "organisation_id": organisation_id,
        **ent,
        "status": org.status,
        "subscription_status": sub.status if sub else None,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
        "evaluated_at": utcnow().isoformat(),
    }


def toggle_module(db: Session, organisation_id: str, module: str, enabled: bool) -> dict:
    org = get_organisation(db, organisation_id)
    profile = load_profiles()[org.academy_type]
    plan = billing.current_plan(db, organisation_id)
    if enabled and module not in compute_entitlement(profile, plan)["modules"]:
        raise TenancyError("module is not in the current plan; upgrade to unlock it", 402)
    with organisation_scope(organisation_id):
        row = db.scalar(
            scoped(db, select(OrganisationModule), OrganisationModule).where(OrganisationModule.module == module)
        )
        if not row:
            row = OrganisationModule(organisation_id=organisation_id, module=module)
            db.add(row)
        row.enabled = enabled
        _changed(db, organisation_id)
    db.commit()
    return entitlement(db, organisation_id)


def _changed(db: Session, organisation_id: str) -> None:
    events.publish(db, "tenancy.entitlement.changed", organisation_id, {"organisation_id": organisation_id})


# ---- super admin ----


def list_organisations(
    db: Session, *, status: str | None = None, plan: str | None = None, academy_type: str | None = None
) -> list[dict]:
    with platform_scope():
        q = select(Organisation).order_by(Organisation.created_at.desc())
        if status:
            q = q.where(Organisation.status == status)
        if academy_type:
            q = q.where(Organisation.academy_type == academy_type)
        orgs = list(db.scalars(q))
        out = []
        for o in orgs:
            sub = billing.get_subscription(db, o.id)
            if plan and (not sub or sub.plan_id != plan):
                continue
            out.append(
                o.to_dict(
                    plan=sub.plan_id if sub else None,
                    trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
                )
            )
        return out


def set_status(db: Session, organisation_id: str, status: str, reason: str) -> Organisation:
    from ..domain.models import STATUSES

    if status not in STATUSES:
        raise TenancyError(f"status must be one of {STATUSES}")
    org = get_organisation(db, organisation_id)
    with platform_scope():
        prev_status = org.status
        org.status, org.status_reason = status, reason
        name = {"active": "activated", "suspended": "suspended", "archived": "archived"}.get(status, "status_changed")
        events.publish(db, f"tenancy.organisation.{name}", org.id, {"organisation_id": org.id, "reason": reason})
        email = _admin_email(db, org.id)
        if email and status == "suspended":
            subject = (
                f"Your Education OS registration for {org.name} was not approved"
                if prev_status == "pending_approval"
                else f"Your Education OS organisation {org.name} has been suspended"
            )
            body = (
                f"Your registration for {org.name} was not approved. Reason: {reason}"
                if prev_status == "pending_approval"
                else f"Your organisation {org.name} status was updated to suspended. Reason: {reason}"
            )
            notify.send_email(
                email,
                subject,
                body,
                organisation_id=org.id,
                status=status,
                reason=reason,
            )
        elif email and status == "active" and prev_status != "active":
            notify.send_email(
                email,
                f"Your Education OS organisation {org.name} has been activated",
                f"Your organisation {org.name} is now active.",
                organisation_id=org.id,
                status=status,
            )
        db.commit()
    return org


def reject(db: Session, organisation_id: str, *, rejected_by: str, reason: str = "") -> Organisation:
    """Super admin rejects an organisation registration awaiting approval."""
    org = get_organisation(db, organisation_id)
    if org.status != "pending_approval":
        raise TenancyError(f"organisation is {org.status}, nothing to reject", 409)
    return set_status(db, organisation_id, "suspended", reason=reason or "registration rejected")


def set_overrides(db: Session, organisation_id: str, grant: list[str], revoke: list[str], reason: str) -> dict:
    get_organisation(db, organisation_id)
    with organisation_scope(organisation_id):
        for module, on in [(m, True) for m in grant] + [(m, False) for m in revoke]:
            row = db.scalar(
                scoped(db, select(OrganisationModule), OrganisationModule).where(OrganisationModule.module == module)
            )
            if not row:
                row = OrganisationModule(organisation_id=organisation_id, module=module)
                db.add(row)
            row.override, row.enabled, row.reason = on, on, reason
        _changed(db, organisation_id)
    db.commit()
    return entitlement(db, organisation_id)


def impersonate(db: Session, *, organisation_id: str, user_id: str, super_admin_id: str, reason: str) -> dict:
    org = get_organisation(db, organisation_id)
    user = identity.get_user(db, user_id)
    if not user or user.organisation_id != org.id:
        raise TenancyError("user is not in that organisation", 404)
    events.publish(
        db,
        "tenancy.impersonation.started",
        org.id,
        {"organisation_id": org.id, "user_id": user_id, "super_admin_id": super_admin_id, "reason": reason},
        actor=super_admin_id,
    )
    db.commit()
    token = create_token(
        user_id=user.id,
        organisation_id=org.id,
        roles=list(user.roles or []),
        impersonated_by=super_admin_id,
        ttl_minutes=60,
    )
    return {"token": token, "expires_in_minutes": 60}
