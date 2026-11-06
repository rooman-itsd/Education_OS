"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "regulatory-reports"
OBLIGATION_MANAGE = f"{MODULE}:obligation:manage"
FILING_MANAGE = f"{MODULE}:filing:manage"
FILING_PREPARE = f"{MODULE}:filing:prepare"
DATA_READ = f"{MODULE}:data:read"
STATS_READ = f"{MODULE}:stats:read"

PERMISSION_KEYS = (OBLIGATION_MANAGE, FILING_MANAGE, FILING_PREPARE, DATA_READ, STATS_READ)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def sees_all_filings(self) -> bool:
        """regulatory-reports:data:read or regulatory-reports:filing:manage see every filing; a preparer only their
        own (contract GET /filings)."""
        return self.can(DATA_READ) or self.can(FILING_MANAGE)

    def sees_all_obligations(self) -> bool:
        """regulatory-reports:data:read or regulatory-reports:obligation:manage see every obligation; a preparer only
        the obligations of their own filings (permissions.yaml filing:prepare)."""
        return self.can(DATA_READ) or self.can(OBLIGATION_MANAGE)


def require(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds one of `permissions`."""
    if not permissions:
        raise ValueError("require() needs at least one permission")
    if not any(actor.can(p) for p in permissions):
        raise forbidden(f"missing permission {' or '.join(permissions)}")


def require_all(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds every one of `permissions` (GET /calendar needs data:read and stats:read)."""
    missing = [p for p in permissions if not actor.can(p)]
    if missing:
        raise forbidden(f"missing permission {' and '.join(missing)}")
