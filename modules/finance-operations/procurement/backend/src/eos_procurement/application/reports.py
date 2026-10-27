"""The purchase-orders-pending report behind the Finance Staff widget."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, money
from ..infrastructure.models import PurchaseOrder, VendorInvoice
from . import service
from .service import _q


def _count_value(rows: list, amount) -> dict:
    return {"count": len(rows), "value": money(sum((Decimal(amount(x)) for x in rows), ZERO))}


def _since(po: PurchaseOrder):
    """When an order started waiting: submitted for approval, or issued for delivery."""
    moment = po.submitted_at if po.status == "submitted" else po.issued_at
    return (moment or po.created_at).date()


def purchase_orders_pending(db: Session) -> dict:
    """Orders awaiting approval, issued orders awaiting delivery (with the overdue ones), approved invoices awaiting
    payment, and the ten oldest pending orders."""
    orders = list(
        db.scalars(_q(db, PurchaseOrder).where(PurchaseOrder.status.in_(("submitted", *rules.OPEN_ORDER_STATUSES))))
    )
    awaiting_approval = [po for po in orders if po.status == "submitted"]
    awaiting_delivery = [po for po in orders if po.status in rules.OPEN_ORDER_STATUSES]
    overdue = [po for po in awaiting_delivery if service._overdue(po)]
    invoices = list(db.scalars(_q(db, VendorInvoice).where(VendorInvoice.status == "approved")))
    names = service._vendor_names(db, {po.vendor_id for po in orders})
    oldest = sorted(orders, key=lambda po: (_since(po), po.number))[:10]
    return {
        "awaiting_approval": _count_value(awaiting_approval, lambda po: po.total),
        "awaiting_delivery": _count_value(awaiting_delivery, lambda po: po.total),
        "overdue_delivery": _count_value(overdue, lambda po: po.total),
        "invoices_awaiting_payment": _count_value(invoices, lambda x: x.amount),
        "oldest": [
            {
                "id": po.id,
                "number": po.number,
                "vendor_name": names.get(po.vendor_id, ""),
                "status": po.status,
                "total": money(po.total),
                "since": _since(po).isoformat(),
            }
            for po in oldest
        ],
    }
