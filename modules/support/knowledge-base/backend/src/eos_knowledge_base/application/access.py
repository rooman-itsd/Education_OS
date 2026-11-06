"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "knowledge-base"
ARTICLE_READ = f"{MODULE}:article:read"
READ_INTERNAL = f"{MODULE}:article:read-internal"
ARTICLE_WRITE = f"{MODULE}:article:write"
ARTICLE_PUBLISH = f"{MODULE}:article:publish"
CATEGORY_MANAGE = f"{MODULE}:category:manage"
STATS_READ = f"{MODULE}:stats:read"

PERMISSION_KEYS = (ARTICLE_READ, READ_INTERNAL, ARTICLE_WRITE, ARTICLE_PUBLISH, CATEGORY_MANAGE, STATS_READ)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def may_read(self, audience: str) -> bool:
        """Audience is enforced on the server in every read (PRD rule): staff articles need read-internal."""
        return audience == "everyone" or self.can(READ_INTERNAL)


def require(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds one of `permissions`."""
    if not permissions:
        raise ValueError("require() needs at least one permission")
    if not any(actor.can(p) for p in permissions):
        raise forbidden(f"missing permission {' or '.join(permissions)}")
