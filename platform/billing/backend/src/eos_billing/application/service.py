from __future__ import annotations

import secrets
from datetime import timedelta

from eos_core import events
from eos_core.config import load_plans
from eos_core.db import scoped, utcnow
from eos_core.settings import settings
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import Invoice, Plan, Subscription


class BillingError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def seed_plans(db: Session) -> None:
    for pid, p in load_plans().items():
        if db.get(Plan, pid) is None:
            db.add(
                Plan(
                    id=pid,
                    title=p["title"],
                    description=p.get("description", ""),
                    price_per_month=p.get("price_per_month", 0),
                    currency=p.get("currency", "INR"),
                    trial_days=p.get("trial_days"),
                    suites=p.get("suites", []),
                    modules=p.get("modules", []),
                    specialized_suites=str(p.get("specialized_suites", 0)),
                    integrations=p.get("integrations", []),
                    limits=p.get("limits", {}),
                    after_trial=p.get("after_trial", "read_only"),
                )
            )
    db.commit()


def list_plans(db: Session, include_unpublished: bool = False) -> list[dict]:
    q = select(Plan).order_by(Plan.price_per_month)
    if not include_unpublished:
        q = q.where(Plan.published.is_(True))
    return [p.to_dict() for p in db.scalars(q)]


def get_plan(db: Session, plan_id: str) -> Plan:
    plan = db.get(Plan, plan_id)
    if not plan:
        raise BillingError(f"unknown plan {plan_id}", 404)
    return plan


def get_subscription(db: Session, organisation_id: str) -> Subscription | None:
    with organisation_scope(organisation_id):
        return db.scalar(scoped(db, select(Subscription), Subscription).order_by(Subscription.created_at.desc()))


def current_plan(db: Session, organisation_id: str) -> dict:
    sub = get_subscription(db, organisation_id)
    plan = get_plan(db, sub.plan_id if sub else "trial")
    return plan.to_rule()


def plan_limits(db: Session, organisation_id: str) -> dict:
    """The organisation's plan limits as config/plans.yaml declares them (users, students, storage_gb). A missing
    or zero entry is no limit."""
    return current_plan(db, organisation_id)["limits"]


def user_limit(db: Session, organisation_id: str) -> int | None:
    """The ceiling on active users, or None for none. apps/backend wires this into identity's
    `hooks.user_limit`, so create_user refuses the user that would exceed it (409 plan_limit_reached)."""
    n = plan_limits(db, organisation_id).get("users")
    return int(n) if n else None


def usage_vs_limits(db: Session, organisation_id: str) -> dict:
    """What the organisation uses against what its plan allows. Users are counted by identity (a declared
    dependency); students and storage have no module counting them yet and are reported as null."""
    from eos_identity.application.service import count_active_users

    plan = current_plan(db, organisation_id)
    limits = plan["limits"]
    usage = {"users": count_active_users(db, organisation_id), "students": None, "storage_gb": None}
    exceeded = [k for k, used in usage.items() if used is not None and limits.get(k) and used >= limits[k]]
    return {"plan": plan["id"], "limits": limits, "usage": usage, "at_limit": exceeded}


def start_trial(db: Session, *, organisation_id: str) -> Subscription:
    plan = get_plan(db, "trial")
    ends = utcnow() + timedelta(days=plan.trial_days or 30)
    sub = Subscription(organisation_id=organisation_id, plan_id="trial", status="trialing", trial_ends_at=ends)
    db.add(sub)
    events.publish(
        db,
        "billing.subscription.started",
        organisation_id,
        {"organisation_id": organisation_id, "plan": "trial", "status": "trialing", "trial_ends_at": ends.isoformat()},
    )
    return sub


def upgrade(db: Session, *, organisation_id: str, plan_id: str, billing_cycle: str = "monthly") -> dict:
    plan = get_plan(db, plan_id)
    if not plan.published:
        raise BillingError("plan is not available", 400)
    sub = get_subscription(db, organisation_id)
    if sub is None:
        raise BillingError("no subscription", 404)
    if sub.plan_id == plan_id and sub.status == "active":
        raise BillingError("already on this plan", 409)
    reference = secrets.token_hex(8)
    with organisation_scope(organisation_id):
        if settings.payment_adapter == "none":
            # No payment adapter configured (dev / pilot): activate immediately and say so.
            _activate(db, sub, plan_id, billing_cycle, reference)
            db.commit()
            return {
                "payment_url": None,
                "reference": reference,
                "activated": True,
                "note": "BILLING_PAYMENT_ADAPTER=none, upgrade applied without payment",
            }
        sub.pending_plan_id, sub.payment_reference = plan_id, reference
        db.commit()
    return {"payment_url": f"/api/v1/billing/pay/{reference}", "reference": reference, "activated": False}


def confirm_payment(db: Session, *, reference: str) -> Subscription:
    with platform_scope():
        sub = db.scalar(select(Subscription).where(Subscription.payment_reference == reference))
    if not sub or not sub.pending_plan_id:
        raise BillingError("unknown payment reference", 404)
    with organisation_scope(sub.organisation_id):
        _activate(db, sub, sub.pending_plan_id, "monthly", reference)
        db.commit()
    return sub


def _activate(db: Session, sub: Subscription, plan_id: str, billing_cycle: str, reference: str) -> None:
    from_plan = sub.plan_id
    days = 365 if billing_cycle == "yearly" else 30
    now = utcnow()
    sub.plan_id, sub.status, sub.pending_plan_id = plan_id, "active", None
    sub.trial_ends_at = None
    sub.current_period_ends_at = now + timedelta(days=days)
    sub.payment_reference = reference
    plan = get_plan(db, plan_id)
    months = 12 if billing_cycle == "yearly" else 1
    db.add(
        Invoice(
            organisation_id=sub.organisation_id,
            subscription_id=sub.id,
            plan_id=plan_id,
            amount=float(plan.price_per_month or 0) * months,
            currency=plan.currency,
            status="paid",
            issued_at=now,
            period_start=now,
            period_end=sub.current_period_ends_at,
            payment_reference=reference,
        )
    )
    events.publish(
        db,
        "billing.subscription.upgraded",
        sub.organisation_id,
        {"organisation_id": sub.organisation_id, "from_plan": from_plan, "to_plan": plan_id},
    )
    events.publish(
        db,
        "tenancy.entitlement.changed",
        sub.organisation_id,
        {"organisation_id": sub.organisation_id, "plan": plan_id},
    )


def list_invoices(db: Session, organisation_id: str) -> list[dict]:
    """The organisation's invoices, newest first."""
    with organisation_scope(organisation_id):
        q = scoped(db, select(Invoice), Invoice).order_by(Invoice.issued_at.desc())
        return [i.to_dict() for i in db.scalars(q)]


def cancel(db: Session, *, organisation_id: str) -> Subscription:
    sub = get_subscription(db, organisation_id)
    if not sub:
        raise BillingError("no subscription", 404)
    with organisation_scope(organisation_id):
        sub.status = "cancelled"
        db.commit()
    return sub


def admin_set(
    db: Session, *, organisation_id: str, plan_id: str | None, trial_ends_at=None, comped_until=None, reason: str = ""
) -> Subscription:
    sub = get_subscription(db, organisation_id)
    if not sub:
        raise BillingError("no subscription", 404)
    with organisation_scope(organisation_id):
        if plan_id:
            get_plan(db, plan_id)
            sub.plan_id = plan_id
            sub.status = "trialing" if plan_id == "trial" else "active"
        if trial_ends_at:
            sub.trial_ends_at = trial_ends_at
        if comped_until:
            sub.comped_until = comped_until
        events.publish(
            db,
            "tenancy.entitlement.changed",
            organisation_id,
            {"organisation_id": organisation_id, "plan": sub.plan_id, "reason": reason},
        )
        db.commit()
    return sub


def expire_trials(db: Session) -> int:
    """Run by the scheduler daily. Trials past their end go read-only or suspended per the plan policy."""
    n = 0
    with platform_scope():
        now = utcnow()
        for sub in db.scalars(select(Subscription).where(Subscription.status == "trialing")):
            if sub.trial_ends_at and sub.trial_ends_at.replace(tzinfo=None) < now.replace(tzinfo=None):
                plan = get_plan(db, sub.plan_id)
                sub.status = "read_only"
                events.publish(
                    db,
                    "billing.trial.expired",
                    sub.organisation_id,
                    {"organisation_id": sub.organisation_id, "after_trial": plan.after_trial},
                )
                n += 1
        db.commit()
    return n
