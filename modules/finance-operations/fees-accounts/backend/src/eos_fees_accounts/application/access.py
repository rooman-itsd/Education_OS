"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "fees-accounts"
FEE_STRUCTURE_READ = f"{MODULE}:fee-structure:read"
FEE_STRUCTURE_MANAGE = f"{MODULE}:fee-structure:manage"
INVOICE_READ = f"{MODULE}:invoice:read"
INVOICE_CREATE = f"{MODULE}:invoice:create"
INVOICE_CANCEL = f"{MODULE}:invoice:cancel"
PAYMENT_RECORD = f"{MODULE}:payment:record"
PAYMENT_REFUND = f"{MODULE}:payment:refund"
CONCESSION_REQUEST = f"{MODULE}:concession:request"
CONCESSION_APPROVE = f"{MODULE}:concession:approve"
LEDGER_READ = f"{MODULE}:ledger:read"
REPORT_READ = f"{MODULE}:report:read"
TARGET_MANAGE = f"{MODULE}:target:manage"
DUES_READ = f"{MODULE}:dues:read"
SELF_READ = f"{MODULE}:self:read"
SELF_PAY = f"{MODULE}:self:pay"

PERMISSION_KEYS = (
    FEE_STRUCTURE_READ,
    FEE_STRUCTURE_MANAGE,
    INVOICE_READ,
    INVOICE_CREATE,
    INVOICE_CANCEL,
    PAYMENT_RECORD,
    PAYMENT_REFUND,
    CONCESSION_REQUEST,
    CONCESSION_APPROVE,
    LEDGER_READ,
    REPORT_READ,
    TARGET_MANAGE,
    DUES_READ,
    SELF_READ,
    SELF_PAY,
)


@dataclass
class Actor:
    """The signed-in user. Until student-information maps users to people, a person's person_id is their identity
    user id, so `/me/*` and "the person it is for" compare person_id with user_id."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)
    token: str = ""

    def can(self, permission: str) -> bool:
        return permission in self.permissions
