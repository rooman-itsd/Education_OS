"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here.

A permission is necessary but not enough for case operations: committee membership is checked by the use cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "grievance"
CASE_FILE = f"{MODULE}:case:file"
CASE_READ_OWN = f"{MODULE}:case:read-own"
CASE_READ = f"{MODULE}:case:read"
CASE_MANAGE = f"{MODULE}:case:manage"
APPEAL_DECIDE = f"{MODULE}:appeal:decide"
COMMITTEE_MANAGE = f"{MODULE}:committee:manage"
STATS_READ = f"{MODULE}:stats:read"

PERMISSION_KEYS = (CASE_FILE, CASE_READ_OWN, CASE_READ, CASE_MANAGE, APPEAL_DECIDE, COMMITTEE_MANAGE, STATS_READ)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def require(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds one of `permissions`."""
    if not permissions:
        raise ValueError("require() needs at least one permission")
    if not any(actor.can(p) for p in permissions):
        raise forbidden(f"missing permission {' or '.join(permissions)}")
