"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "procurement"
VENDOR_READ = f"{MODULE}:vendor:read"
VENDOR_MANAGE = f"{MODULE}:vendor:manage"
INDENT_CREATE = f"{MODULE}:indent:create"
INDENT_APPROVE = f"{MODULE}:indent:approve"
TENDER_MANAGE = f"{MODULE}:tender:manage"
PURCHASE_ORDER_READ = f"{MODULE}:purchase-order:read"
PURCHASE_ORDER_MANAGE = f"{MODULE}:purchase-order:manage"
PURCHASE_ORDER_APPROVE = f"{MODULE}:purchase-order:approve"
GOODS_RECEIPT_RECORD = f"{MODULE}:goods-receipt:record"
VENDOR_INVOICE_MANAGE = f"{MODULE}:vendor-invoice:manage"
VENDOR_INVOICE_APPROVE = f"{MODULE}:vendor-invoice:approve"
VENDOR_INVOICE_PAY = f"{MODULE}:vendor-invoice:pay"
REPORT_READ = f"{MODULE}:report:read"

PERMISSION_KEYS = (
    VENDOR_READ,
    VENDOR_MANAGE,
    INDENT_CREATE,
    INDENT_APPROVE,
    TENDER_MANAGE,
    PURCHASE_ORDER_READ,
    PURCHASE_ORDER_MANAGE,
    PURCHASE_ORDER_APPROVE,
    GOODS_RECEIPT_RECORD,
    VENDOR_INVOICE_MANAGE,
    VENDOR_INVOICE_APPROVE,
    VENDOR_INVOICE_PAY,
    REPORT_READ,
)


@dataclass
class Actor:
    """The signed-in user. `token` is forwarded to budget-grants for the availability check."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)
    token: str = ""

    def can(self, permission: str) -> bool:
        return permission in self.permissions
