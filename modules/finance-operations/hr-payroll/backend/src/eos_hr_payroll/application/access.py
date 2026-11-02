"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "hr-payroll"
EMPLOYEE_READ = f"{MODULE}:employee:read"
EMPLOYEE_MANAGE = f"{MODULE}:employee:manage"
LEAVE_TYPE_MANAGE = f"{MODULE}:leave-type:manage"
LEAVE_APPROVE = f"{MODULE}:leave:approve"
PAYROLL_READ = f"{MODULE}:payroll:read"
PAYROLL_PREPARE = f"{MODULE}:payroll:prepare"
PAYROLL_APPROVE = f"{MODULE}:payroll:approve"
APPRAISAL_REVIEW = f"{MODULE}:appraisal:review"
REPORT_READ = f"{MODULE}:report:read"
SELF_USE = f"{MODULE}:self:use"

PERMISSION_KEYS = (
    EMPLOYEE_READ,
    EMPLOYEE_MANAGE,
    LEAVE_TYPE_MANAGE,
    LEAVE_APPROVE,
    PAYROLL_READ,
    PAYROLL_PREPARE,
    PAYROLL_APPROVE,
    APPRAISAL_REVIEW,
    REPORT_READ,
    SELF_USE,
)


@dataclass
class Actor:
    """The signed-in user. An employee is linked to their platform/identity user by `Employee.user_id`."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions
