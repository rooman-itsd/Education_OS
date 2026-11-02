"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "e-office"
FILE_USE = f"{MODULE}:file:use"
FILE_CREATE = f"{MODULE}:file:create"
FILE_DECIDE = f"{MODULE}:file:decide"
FILE_READ_ALL = f"{MODULE}:file:read-all"
CORRESPONDENCE_MANAGE = f"{MODULE}:correspondence:manage"
REPORT_READ = f"{MODULE}:report:read"
SETTINGS_MANAGE = f"{MODULE}:settings:manage"

PERMISSION_KEYS = (
    FILE_USE,
    FILE_CREATE,
    FILE_DECIDE,
    FILE_READ_ALL,
    CORRESPONDENCE_MANAGE,
    REPORT_READ,
    SETTINGS_MANAGE,
)


@dataclass
class Actor:
    """The signed-in user."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions
