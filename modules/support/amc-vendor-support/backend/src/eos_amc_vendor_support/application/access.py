"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "amc-vendor-support"
CONTRACT_READ = f"{MODULE}:contract:read"
CONTRACT_MANAGE = f"{MODULE}:contract:manage"
ENGAGEMENT_MANAGE = f"{MODULE}:engagement:manage"

PERMISSION_KEYS = (CONTRACT_READ, CONTRACT_MANAGE, ENGAGEMENT_MANAGE)


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
