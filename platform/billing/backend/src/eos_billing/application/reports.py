"""The super admin's subscription and revenue report (GET /admin/reports/subscriptions, platform:revenue:read).

Across every organisation, so it runs in platform scope, as the trial jobs do. Money is computed with Decimal and
returned as strings with two decimals ("12500.00"), never as floats. Monthly recurring revenue counts only active
subscriptions at their plan's monthly price; "paid in the last 30 days" sums paid invoices issued in that window,
whatever their billing cycle."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from eos_core.db import utcnow
from eos_core.tenant import platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import Invoice, Plan, Subscription
from . import organisations

STATUSES = ("trialing", "active", "past_due", "read_only", "cancelled")
TRIAL_WINDOW_DAYS = 14
PAID_WINDOW_DAYS = 30
CENT = Decimal("0.01")


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def subscription_report(db: Session) -> dict:
    now = utcnow()
    with platform_scope():
        plans = list(db.scalars(select(Plan).order_by(Plan.price_per_month, Plan.id)))
        subs = list(db.scalars(select(Subscription)))
        since = now - timedelta(days=PAID_WINDOW_DAYS)
        paid = [
            i
            for i in db.scalars(select(Invoice).where(Invoice.status == "paid"))
            if i.issued_at and i.issued_at.replace(tzinfo=None) >= since.replace(tzinfo=None)
        ]

        rows: dict[str, dict] = {}
        for p in plans:
            rows[p.id] = {
                "plan": p.id,
                "title": p.title,
                "currency": p.currency,
                "price_per_month": Decimal(str(p.price_per_month or 0)),
                "subscriptions": dict.fromkeys(STATUSES, 0),
                "paid": Decimal("0"),
            }
        for s in subs:
            # A subscription on a plan that was since deleted still counts, under its plan id.
            row = rows.setdefault(
                s.plan_id,
                {
                    "plan": s.plan_id,
                    "title": s.plan_id,
                    "currency": "INR",
                    "price_per_month": Decimal("0"),
                    "subscriptions": dict.fromkeys(STATUSES, 0),
                    "paid": Decimal("0"),
                },
            )
            status = s.status if s.status in STATUSES else "cancelled"
            row["subscriptions"][status] += 1
        for i in paid:
            if i.plan_id in rows:
                rows[i.plan_id]["paid"] += Decimal(str(i.amount or 0))

        report_plans = []
        for row in rows.values():
            counts = row["subscriptions"]
            report_plans.append(
                {
                    "plan": row["plan"],
                    "title": row["title"],
                    "currency": row["currency"],
                    "subscriptions": counts,
                    "total": sum(counts.values()),
                    "monthly_recurring": _money(row["price_per_month"] * counts["active"]),
                    "paid_last_30_days": _money(row["paid"]),
                }
            )

        today = now.date()
        expiring = []
        for s in subs:
            if s.status != "trialing" or not s.trial_ends_at:
                continue
            days_left = (s.trial_ends_at.date() - today).days
            if 0 <= days_left <= TRIAL_WINDOW_DAYS:
                expiring.append(
                    {
                        "organisation_id": s.organisation_id,
                        "organisation_name": organisations.name(db, s.organisation_id),
                        "plan": s.plan_id,
                        "trial_ends_at": s.trial_ends_at.isoformat(),
                        "days_left": days_left,
                    }
                )
        expiring.sort(key=lambda t: (t["trial_ends_at"], t["organisation_id"]))

    return {
        "generated_at": now.isoformat(),
        "plans": report_plans,
        "trials_expiring": expiring,
        "trial_window_days": TRIAL_WINDOW_DAYS,
        "paid_window_days": PAID_WINDOW_DAYS,
    }
