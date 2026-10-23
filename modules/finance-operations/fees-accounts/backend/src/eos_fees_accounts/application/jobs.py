"""The daily sweep. Until platform/scheduler exists, the host calls `run_daily(db)` once a day."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import money
from ..infrastructure.models import Invoice
from . import service


def _rule_of(raw: dict | None) -> rules.LateFeeRule | None:
    if not raw:
        return None
    cap = raw.get("cap")
    return rules.LateFeeRule(
        raw["kind"], Decimal(raw["amount"]), int(raw.get("grace_days") or 0), Decimal(cap) if cap else None
    )


def run_daily(db: Session, day: date | None = None) -> dict:
    """For every unpaid invoice past its due date: raise its late fee to what the structure's rule says today, and
    publish fees-accounts.invoice.overdue once. Each invoice is handled in its own organisation's scope."""
    day = day or service.today()
    with platform_scope():
        candidates = [
            (i.id, i.organisation_id)
            for i in db.scalars(
                select(Invoice).where(Invoice.status.in_(rules.OPEN_INVOICE_STATUSES), Invoice.due_date < day)
            )
        ]
        db.commit()
    counts = {"overdue_published": 0, "late_fees_updated": 0}
    for invoice_id, org in candidates:
        with organisation_scope(org):
            inv = db.scalar(service._q(db, Invoice).where(Invoice.id == invoice_id).with_for_update())
            if inv is None or inv.status not in rules.OPEN_INVOICE_STATUSES or service.balance_of(inv) <= 0:
                db.rollback()
                continue
            fee = rules.late_fee(_rule_of(inv.late_fee_rule), inv.due_date, day)
            if fee > Decimal(inv.late_fee):
                inv.late_fee, inv.late_fee_updated_on = fee, day
                counts["late_fees_updated"] += 1
            if not inv.overdue_notified:
                inv.overdue_notified = True
                service._publish(
                    db,
                    "invoice.overdue",
                    org,
                    {
                        "invoice_id": inv.id,
                        "person_id": inv.person_id,
                        "balance": money(service.balance_of(inv)),
                        "due_date": inv.due_date.isoformat(),
                    },
                )
                counts["overdue_published"] += 1
            db.commit()
    return counts
