from __future__ import annotations

import os
import re
import secrets
from datetime import UTC, datetime, timedelta

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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..domain.models import Organisation, OrganisationModule, RegistrationToken
from . import tables

AUTO_APPROVE = settings.auto_approve  # module-level so tests can flip it
clock = utcnow  # module-level so tests can move time past the retention period
EXPORT_SCHEMA_VERSION = 1
DEFAULT_RETENTION_DAYS = 30
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
    """The address that registered the organisation: every registration leaves a token row with it."""
    with platform_scope():
        return db.scalar(
            select(RegistrationToken.email)
            .where(RegistrationToken.organisation_id == organisation_id)
            .order_by(RegistrationToken.expires_at.desc())
        )


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
        rejected = prev_status in ("pending_verification", "pending_approval") and status in ("archived", "suspended")
        if email and rejected:
            notify.send_email(
                email,
                f"Your Education OS registration for {org.name} was not approved",
                f"Your registration for {org.name} was not approved. Reason: {reason}",
                organisation_id=org.id,
                status=status,
                reason=reason,
            )
        elif email and status in ("suspended", "archived") and prev_status == "active":
            notify.send_email(
                email,
                f"Your Education OS organisation {org.name} has been {status}",
                f"Your organisation {org.name} status was updated to {status}. Reason: {reason}",
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


def reject(db: Session, organisation_id: str, *, rejected_by: str, reason: str = "") -> Organisation:  # noqa: ARG001
    """Super admin refuses a registration awaiting approval: the organisation is archived (closed for good,
    as the admin console's approval queue does through PUT /status) and the registering address is told why."""
    org = get_organisation(db, organisation_id)
    if org.status != "pending_approval":
        raise TenancyError(f"organisation is {org.status}, nothing to reject", 409)
    return set_status(db, organisation_id, "archived", reason=reason or "registration rejected")


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


# ---- export and deletion with retention (DPDP, ADR-0005 "exports and deletion must work per organisation") ----


def retention_days() -> int:
    """How long an archived organisation's rows are kept before a purge may run. EOS_ORGANISATION_RETENTION_DAYS."""
    return int(os.environ.get("EOS_ORGANISATION_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))


def _aware(moment: datetime) -> datetime:
    """SQLite hands timezone-aware columns back naive; everything stored here is UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def export_organisation(db: Session, organisation_id: str, *, actor: str) -> dict:
    """Everything the platform holds about one organisation: its record and, for every table that carries
    organisation_id (known models and any other table in the database), its rows as column -> JSON-safe value.
    Secrets (password hashes, tokens) are redacted. `files` lists document references; the files themselves follow
    once platform/documents exists. Runs in platform scope and leaves an audit event in the outbox."""
    org = get_organisation(db, organisation_id)
    with platform_scope():
        exported: dict[str, list[dict]] = {}
        references: list[dict] = []
        for table in [tables.organisation_row_table(), *tables.organisation_tables(db)]:
            rows = tables.export_rows(db, table, organisation_id)
            exported[table.name] = rows
            references += tables.file_references(table.name, rows)
        exported_at = clock()
        events.publish(
            db,
            "tenancy.organisation.exported",
            org.id,
            {
                "organisation_id": org.id,
                "actor": actor,
                "tables": len(exported),
                "rows": sum(len(r) for r in exported.values()),
            },
            actor=actor,
        )
        db.commit()
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": exported_at.isoformat(),
        "exported_by": actor,
        "organisation": org.to_dict(),
        "row_counts": {name: len(rows) for name, rows in exported.items()},
        "tables": exported,
        "files": {
            "note": "platform/documents is not built yet: these are references only; the files follow once it exists.",
            "references": references,
        },
    }


def _has_paid_invoices(db: Session, organisation_id: str) -> bool:
    return any(i["status"] == "paid" for i in billing.list_invoices(db, organisation_id))


def request_deletion(
    db: Session, organisation_id: str, *, requested_by: str, reason: str = "", confirm_slug: str | None = None
) -> Organisation:
    """Archive the organisation and start the retention clock. Its users cannot sign in from now on (identity
    refuses any status but active). An active organisation with paid invoices is refused unless confirm_slug
    names it, so a paying customer is never archived by a slip."""
    org = get_organisation(db, organisation_id)
    if org.delete_after is not None:
        raise TenancyError(f"deletion already requested; rows are purged after {org.delete_after.isoformat()}", 409)
    if org.status == "active" and _has_paid_invoices(db, org.id) and confirm_slug != org.slug:
        raise TenancyError(
            "organisation is active with paid invoices; repeat the request with confirm_slug set to its slug", 409
        )
    now = clock()
    with platform_scope():
        org.status_before_deletion, org.status = org.status, "archived"
        org.status_reason = reason or "deletion requested"
        org.delete_after = now + timedelta(days=retention_days())
        org.deletion_requested_by, org.deletion_requested_at = requested_by, now
        payload = {
            "organisation_id": org.id,
            "reason": org.status_reason,
            "delete_after": org.delete_after.isoformat(),
            "requested_by": requested_by,
        }
        events.publish(db, "tenancy.organisation.archived", org.id, payload, actor=requested_by)
        events.publish(db, "tenancy.organisation.deletion_requested", org.id, payload, actor=requested_by)
        email = _admin_email(db, org.id)
        if email:
            notify.send_email(
                email,
                f"Your Education OS organisation {org.name} has been archived",
                f"Your organisation {org.name} has been archived and its users can no longer sign in. Its data is "
                f"kept until {org.delete_after.date().isoformat()} and deleted after that unless the organisation "
                f"is restored. Reason: {org.status_reason}",
                organisation_id=org.id,
                status="archived",
                delete_after=org.delete_after.isoformat(),
            )
        db.commit()
    return org


def restore_organisation(db: Session, organisation_id: str, *, actor: str) -> Organisation:
    """Undo a deletion request before the purge runs: the previous status comes back, the clock stops."""
    org = get_organisation(db, organisation_id)
    if org.delete_after is None:
        raise TenancyError("no deletion is pending for this organisation", 409)
    with platform_scope():
        org.status = org.status_before_deletion or "active"
        org.status_reason = "restored"
        org.delete_after = org.deletion_requested_by = org.deletion_requested_at = org.status_before_deletion = None
        events.publish(
            db,
            "tenancy.organisation.restored",
            org.id,
            {"organisation_id": org.id, "status": org.status, "restored_by": actor},
            actor=actor,
        )
        if org.status == "active":
            events.publish(db, "tenancy.organisation.activated", org.id, {"organisation_id": org.id})
        db.commit()
    return org


def purge_organisation(db: Session, organisation_id: str, *, actor: str, force: bool = False) -> dict:
    """Delete every row of the organisation in every table that carries organisation_id, then the organisation
    itself. Only after delete_after has passed, or with force. Irreversible; the outbox keeps one platform-level
    event recording what was removed (counts, no personal data)."""
    org = get_organisation(db, organisation_id)
    if org.delete_after is None:
        raise TenancyError("deletion has not been requested for this organisation", 409)
    now = clock()
    if not force and now < _aware(org.delete_after):
        raise TenancyError(f"retention runs until {org.delete_after.isoformat()}; pass force to purge now", 409)
    slug = org.slug
    requested_by = org.deletion_requested_by
    requested_at = _aware(org.deletion_requested_at).isoformat() if org.deletion_requested_at else None
    with platform_scope():
        try:
            counts = tables.delete_rows(db, tables.organisation_tables(db), org.id)
            db.execute(tables.organisation_row_table().delete().where(tables.organisation_row_table().c.id == org.id))
        except tables.PurgeBlockedError as e:
            db.rollback()
            raise TenancyError(
                f"purge_blocked: foreign keys block deleting rows from {', '.join(e.tables)}", 409
            ) from e
        except SQLAlchemyError as e:
            db.rollback()
            raise TenancyError(
                "purge_blocked: the database refused the delete (" + type(e).__name__ + "); nothing was deleted", 409
            ) from e
        except Exception:
            db.rollback()
            raise
        db.expunge(org)
        result = {
            "organisation_id": organisation_id,
            "slug": slug,
            "purged_at": now.isoformat(),
            "forced": force,
            "rows_deleted": {name: n for name, n in sorted(counts.items()) if n},
        }
        # The tenant no longer exists, so this one record is the platform's, not the organisation's.
        events.publish(
            db,
            "tenancy.organisation.purged",
            None,
            {**result, "purged_by": actor, "requested_by": requested_by, "requested_at": requested_at},
            actor=actor,
        )
        db.commit()
    return result
