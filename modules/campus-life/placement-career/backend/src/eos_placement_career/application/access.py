"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "placement-career"
COMPANY_READ = f"{MODULE}:company:read"
COMPANY_MANAGE = f"{MODULE}:company:manage"
DRIVE_MANAGE = f"{MODULE}:drive:manage"
OPENING_READ = f"{MODULE}:opening:read"
OPENING_MANAGE = f"{MODULE}:opening:manage"
APPLICATION_READ = f"{MODULE}:application:read"
APPLICATION_MANAGE = f"{MODULE}:application:manage"
REPORT_READ = f"{MODULE}:report:read"
SELF_READ = f"{MODULE}:self:read"
SELF_APPLY = f"{MODULE}:self:apply"

PERMISSION_KEYS = (
    COMPANY_READ,
    COMPANY_MANAGE,
    DRIVE_MANAGE,
    OPENING_READ,
    OPENING_MANAGE,
    APPLICATION_READ,
    APPLICATION_MANAGE,
    REPORT_READ,
    SELF_READ,
    SELF_APPLY,
)


@dataclass
class Actor:
    """The signed-in user. `name` is the token's `name` claim, empty when the token has none."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)
    name: str = ""

    def can(self, permission: str) -> bool:
        return permission in self.permissions
