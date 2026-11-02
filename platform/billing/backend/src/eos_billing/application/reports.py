"""The super admin's subscription and revenue report (GET /admin/reports/subscriptions, platform:revenue:read).

Across every organisation, so it runs in platform scope, as the trial jobs do. Money is computed with Decimal and
returned as strings with two decimals ("12500.00"), never as floats. Monthly recurring revenue counts only active
subscriptions that pay: one comped by the super admin (admin_set, comped_until in the future) is active but brings
in nothing, so it is counted apart, as `comped`. "Paid in the last 30 days" sums paid invoices issued in that window,
whatever their billing cycle. Trials ending within 14 days include those already past their end that the daily
expiry job has not turned read-only yet (negative days_left), so none is invisible for up to a day."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from eos_core.db import utcnow
from eos_core.tenant import platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import Invoice, Plan, Subscription
from . import organisations

STATUSES = ("trialing", "active", "past_due", "read_only", "cancelled")
# A status outside the contract's five (written by a future change, or by hand) is counted, never relabelled.
OTHER = "other"
TRIAL_WINDOW_DAYS = 14
PAID_WINDOW_DAYS = 30
CENT = Decimal("0.01")


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def _naive(value: datetime) -> datetime:
    """SQLite returns naive datetimes and Postgres aware ones, both UTC: compare them without the zone."""
    return value.replace(tzinfo=None)


def _utc(value: datetime) -> datetime:
    """The UTC moment, whatever zone the database connection returned it in (SQLite: naive, already UTC)."""
    return value if value.tzinfo is None else value.astimezone(UTC)


def _comped(sub: Subscription, now: datetime) -> bool:
    return sub.comped_until is not None and _naive(sub.comped_until) > _naive(now)


def subscription_report(db: Session) -> dict:
    now = utcnow()
    with platform_scope():
        plans = list(db.scalars(select(Plan).order_by(Plan.price_per_month, Plan.id)))
        subs = list(db.scalars(select(Subscription)))
        since = now - timedelta(days=PAID_WINDOW_DAYS)
        # Filtered in the database: only the window's paid invoices are loaded, never every invoice ever written.
        paid = list(db.scalars(select(Invoice).where(Invoice.status == "paid", Invoice.issued_at >= since)))

        def new_row(plan_id: str, title: str, currency: str, price: Decimal) -> dict:
            return {
                "plan": plan_id,
                "title": title,
                "currency": currency,
                "price_per_month": price,
                "subscriptions": dict.fromkeys((*STATUSES, OTHER), 0),
                "comped": 0,
                "paid": Decimal("0"),
            }

        rows: dict[str, dict] = {
            p.id: new_row(p.id, p.title, p.currency, Decimal(str(p.price_per_month or 0))) for p in plans
        }
        # A subscription or a paid invoice on a plan that was since deleted still counts, under its plan id: money
        # that came in is never dropped from the report.
        for s in subs:
            row = rows.setdefault(s.plan_id, new_row(s.plan_id, s.plan_id, "INR", Decimal("0")))
            status = s.status if s.status in STATUSES else OTHER
            row["subscriptions"][status] += 1
            if status == "active" and _comped(s, now):
                row["comped"] += 1
        for i in paid:
            row = rows.setdefault(i.plan_id, new_row(i.plan_id, i.plan_id, i.currency or "INR", Decimal("0")))
            row["paid"] += Decimal(str(i.amount or 0))

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
                    # Active and comped: counted in `active`, but paying nothing, so not in the recurring revenue.
                    "comped": row["comped"],
                    "monthly_recurring": _money(row["price_per_month"] * (counts["active"] - row["comped"])),
                    "paid_last_30_days": _money(row["paid"]),
                }
            )

        today = now.date()
        expiring = []
        for s in subs:
            if s.status != "trialing" or not s.trial_ends_at:
                continue
            days_left = (_utc(s.trial_ends_at).date() - today).days
            if days_left <= TRIAL_WINDOW_DAYS:  # negative: ended, waiting for the daily expiry job
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
