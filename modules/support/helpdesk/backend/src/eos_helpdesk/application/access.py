"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for), as facility-booking does. Which profile roles
receive the module roles is not decided here."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "helpdesk"
TICKET_READ = f"{MODULE}:ticket:read"
TICKET_READ_ALL = f"{MODULE}:ticket:read-all"
TICKET_WORK = f"{MODULE}:ticket:work"
TICKET_MANAGE = f"{MODULE}:ticket:manage"
SETTINGS_MANAGE = f"{MODULE}:settings:manage"
SELF_READ = f"{MODULE}:self:read"
SELF_RAISE = f"{MODULE}:self:raise"

PERMISSION_KEYS = (
    TICKET_READ,
    TICKET_READ_ALL,
    TICKET_WORK,
    TICKET_MANAGE,
    SETTINGS_MANAGE,
    SELF_READ,
    SELF_RAISE,
)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def require(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds one of `permissions`. Some operations accept any of several keys, for example
    GET /queues: "helpdesk:ticket:read or helpdesk:settings:manage"."""
    if not permissions:
        raise ValueError("require() needs at least one permission")
    if not any(actor.can(p) for p in permissions):
        raise forbidden(f"missing permission {' or '.join(permissions)}")
