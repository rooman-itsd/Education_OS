from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from eos_core import events
from eos_core.config import load_plans
from eos_core.db import scoped, utcnow
from eos_core.settings import settings
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import gst
from ..domain.models import BillingProfile, Invoice, InvoiceCounter, Plan, Subscription, TrialReminder
from . import config


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
    taxable = gst.money(Decimal(str(plan.price_per_month or 0)) * months)
    db.add(
        Invoice(
            organisation_id=sub.organisation_id,
            subscription_id=sub.id,
            plan_id=plan_id,
            amount=taxable,
            currency=plan.currency,
            status="paid",
            issued_at=now,
            period_start=now,
            period_end=sub.current_period_ends_at,
            payment_reference=reference,
            **_tax_fields(db, sub.organisation_id, taxable, now),
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


def _next_number(db: Session, prefix: str, fy: str) -> str:
    """The next number of the series for a financial year, taken under a row lock inside the caller's transaction."""
    counter = db.scalar(select(InvoiceCounter).where(InvoiceCounter.financial_year == fy).with_for_update())
    if counter is None:
        try:
            with db.begin_nested():
                db.add(InvoiceCounter(financial_year=fy, last_sequence=0))
                db.flush()
        except IntegrityError:
            pass  # another transaction created the year's row first
        counter = db.scalar(select(InvoiceCounter).where(InvoiceCounter.financial_year == fy).with_for_update())
    counter.last_sequence += 1
    db.flush()
    return gst.invoice_number(prefix, fy, counter.last_sequence)


def _tax_fields(db: Session, organisation_id: str, taxable: Decimal, issued_at: datetime) -> dict:
    """The GST columns of an invoice: parties, place of supply, SAC, the tax heads and the number.

    With no supplier GSTIN configured (development, pilots) the invoice carries no tax: scheme 'none', total equal
    to the taxable value, and still a number, so the series is the same everywhere."""
    try:
        cfg = config.invoicing()
    except gst.GstError as e:
        raise BillingError(f"invoicing is not configured correctly: {e}", 503) from e
    fy = gst.financial_year(issued_at)
    profile = get_profile(db, organisation_id)
    fields: dict = {
        "financial_year": fy,
        "sac_code": cfg.sac_code,
        "recipient_name": profile.legal_name if profile else None,
        "recipient_gstin": profile.gstin if profile else None,
        "recipient_address": profile.address if profile else None,
        "recipient_state_code": profile.state_code if profile else None,
    }
    if cfg.supplier is None:
        zero = Decimal("0.00")
        fields.update(
            tax_scheme="none",
            gst_rate=Decimal("0.00"),
            taxable_value=taxable,
            cgst_amount=zero,
            sgst_amount=zero,
            igst_amount=zero,
            total_amount=taxable,
        )
    else:
        supplier = cfg.supplier
        pos = gst.place_of_supply(profile.state_code if profile else None, supplier.state_code)
        tax = gst.compute_tax(taxable, cfg.gst_rate, intra_state=pos == supplier.state_code)
        fields.update(
            tax_scheme=tax.scheme,
            gst_rate=tax.rate,
            taxable_value=tax.taxable_value,
            cgst_amount=tax.cgst,
            sgst_amount=tax.sgst,
            igst_amount=tax.igst,
            total_amount=tax.total,
            place_of_supply=pos,
            supplier_name=supplier.name,
            supplier_gstin=supplier.gstin,
            supplier_address=supplier.address,
            supplier_state_code=supplier.state_code,
        )
    fields["invoice_number"] = _next_number(db, cfg.prefix, fy)
    return fields


def get_profile(db: Session, organisation_id: str) -> BillingProfile | None:
    with organisation_scope(organisation_id):
        return db.scalar(scoped(db, select(BillingProfile), BillingProfile))


def save_profile(
    db: Session,
    *,
    organisation_id: str,
    legal_name: str,
    gstin: str | None,
    address: str,
    state_code: str | None,
) -> BillingProfile:
    """Set who invoices are addressed to. A GSTIN must be valid (format and check character) and fixes the state;
    an explicit state code that disagrees with it is refused. With no GSTIN the state code is optional: invoices
    then go to the consumer's state, or the supplier's when none is given."""
    try:
        number = gst.normalise_gstin(gstin)
        number = gst.validate_gstin(number) if number else None
        state = (state_code or "").strip() or None
        if state:
            gst.validate_state_code(state)
        if number:
            if state and state != gst.state_code(number):
                raise gst.GstError("state code does not match the state in the GSTIN")
            state = gst.state_code(number)
    except gst.GstError as e:
        raise BillingError(str(e), 422) from e
    name = (legal_name or "").strip()
    if not name:
        raise BillingError("legal name is required", 422)
    with organisation_scope(organisation_id):
        profile = db.scalar(scoped(db, select(BillingProfile), BillingProfile))
        if profile is None:
            profile = BillingProfile(organisation_id=organisation_id)
            db.add(profile)
        profile.legal_name, profile.gstin, profile.address, profile.state_code = (
            name,
            number,
            (address or "").strip(),
            state,
        )
        db.commit()
    return profile


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
            if sub.trial_ends_at and _utc(sub.trial_ends_at) < now:
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


REMINDER_DAYS = (7, 3, 1)


def _utc(moment: datetime) -> datetime:
    """Stored times are UTC; SQLite hands them back naive, PostgreSQL in the session's time zone."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def due_threshold(days_left: int) -> int | None:
    """The most urgent reminder due with days_left whole days to go: 7 from 7 to 4 days, 3 at 3 and 2, 1 at 1.
    None before the first threshold and once the trial has ended (expire_trials takes over)."""
    if days_left < 1:
        return None
    due = [t for t in REMINDER_DAYS if t >= days_left]
    return min(due) if due else None


def remind_trials(db: Session) -> int:
    """Run by the scheduler daily: billing.trial.expiring 7, 3 and 1 whole days (UTC) before a trial ends.

    Each run raises, per trial, the most urgent threshold that is due and not raised yet (billing_trial_reminder).
    A reminder missed on its day (the scheduler was down, the run failed) therefore goes out on the next run, with
    the real days left; one superseded by a more urgent one is not sent late. A second run raises nothing again,
    and two runs at once cannot both raise it (the row's unique key decides). The `reminder_key` (organisation,
    trial end date, threshold) also lets a consumer send each reminder once."""
    n = 0
    with platform_scope():
        today = utcnow().date()
        for sub in db.scalars(select(Subscription).where(Subscription.status == "trialing")):
            if not sub.trial_ends_at:
                continue
            ends_on = _utc(sub.trial_ends_at).date()
            days_left = (ends_on - today).days
            threshold = due_threshold(days_left)
            if threshold is None:
                continue
            try:
                with db.begin_nested():
                    db.add(
                        TrialReminder(
                            organisation_id=sub.organisation_id,
                            trial_ends_on=ends_on.isoformat(),
                            threshold=threshold,
                            days_left=days_left,
                        )
                    )
                    db.flush()
            except IntegrityError:
                continue  # raised already, by an earlier run or one running now
            events.publish(
                db,
                "billing.trial.expiring",
                sub.organisation_id,
                {
                    "organisation_id": sub.organisation_id,
                    "days_left": days_left,
                    "threshold": threshold,
                    "trial_ends_on": ends_on.isoformat(),
                    "reminder_key": f"{sub.organisation_id}:{ends_on.isoformat()}:{threshold}",
                },
            )
            n += 1
        db.commit()
    return n
