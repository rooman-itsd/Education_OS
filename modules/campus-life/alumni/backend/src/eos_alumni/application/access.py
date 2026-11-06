"""Who is calling, and the permission keys of contracts/permissions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "alumni"
DIRECTORY_READ = f"{MODULE}:directory:read"
DIRECTORY_MANAGE = f"{MODULE}:directory:manage"
MENTORING_READ = f"{MODULE}:mentoring:read"
MENTORING_MANAGE = f"{MODULE}:mentoring:manage"
SELF_READ = f"{MODULE}:self:read"

PERMISSION_KEYS = (DIRECTORY_READ, DIRECTORY_MANAGE, MENTORING_READ, MENTORING_MANAGE, SELF_READ)


@dataclass
class Actor:
    """The signed-in user."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions
