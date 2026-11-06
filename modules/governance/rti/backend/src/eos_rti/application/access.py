"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "rti"
REQUEST_READ = f"{MODULE}:request:read"
REQUEST_MANAGE = f"{MODULE}:request:manage"
REFERRAL_RESPOND = f"{MODULE}:referral:respond"
APPEAL_DECIDE = f"{MODULE}:appeal:decide"
STATS_READ = f"{MODULE}:stats:read"

PERMISSION_KEYS = (REQUEST_READ, REQUEST_MANAGE, REFERRAL_RESPOND, APPEAL_DECIDE, STATS_READ)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions
