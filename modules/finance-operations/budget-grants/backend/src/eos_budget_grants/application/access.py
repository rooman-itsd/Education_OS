"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "budget-grants"
BUDGET_READ = f"{MODULE}:budget:read"
BUDGET_MANAGE = f"{MODULE}:budget:manage"
BUDGET_APPROVE = f"{MODULE}:budget:approve"
AVAILABILITY_READ = f"{MODULE}:availability:read"
EXPENDITURE_RECORD = f"{MODULE}:expenditure:record"
GRANT_READ = f"{MODULE}:grant:read"
GRANT_MANAGE = f"{MODULE}:grant:manage"
UTILISATION_APPROVE = f"{MODULE}:utilisation:approve"
REPORT_READ = f"{MODULE}:report:read"
SELF_READ = f"{MODULE}:self:read"

PERMISSION_KEYS = (
    BUDGET_READ,
    BUDGET_MANAGE,
    BUDGET_APPROVE,
    AVAILABILITY_READ,
    EXPENDITURE_RECORD,
    GRANT_READ,
    GRANT_MANAGE,
    UTILISATION_APPROVE,
    REPORT_READ,
    SELF_READ,
)


@dataclass
class Actor:
    """The signed-in user. Investigators are identity users (Investigator.user_id in the contract)."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions
