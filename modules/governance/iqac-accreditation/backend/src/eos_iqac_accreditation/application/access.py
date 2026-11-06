"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves the
caller's keys through the platform (eos_core.config.permissions_for). Which profile roles hold the module roles is
decided by the dashboard layouts in platform/identity/config/dashboards (module_roles), not here."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "iqac-accreditation"
FRAMEWORK_MANAGE = f"{MODULE}:framework:manage"
CYCLE_MANAGE = f"{MODULE}:cycle:manage"
RESPONSE_SUBMIT = f"{MODULE}:response:submit"
ACTION_ITEM_MANAGE = f"{MODULE}:action-item:manage"
ACTION_ITEM_UPDATE_OWN = f"{MODULE}:action-item:update-own"
DATA_READ = f"{MODULE}:data:read"
STATS_READ = f"{MODULE}:stats:read"

PERMISSION_KEYS = (
    FRAMEWORK_MANAGE,
    CYCLE_MANAGE,
    RESPONSE_SUBMIT,
    ACTION_ITEM_MANAGE,
    ACTION_ITEM_UPDATE_OWN,
    DATA_READ,
    STATS_READ,
)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def sees_all_responses(self) -> bool:
        """iqac-accreditation:data:read or :cycle:manage see every response; with only :response:submit, the caller's
        own (contract GET /responses)."""
        return self.can(DATA_READ) or self.can(CYCLE_MANAGE)

    def sees_all_action_items(self) -> bool:
        """iqac-accreditation:data:read or :action-item:manage see every action item; with only :update-own, the
        caller's own (contract GET /action-items)."""
        return self.can(DATA_READ) or self.can(ACTION_ITEM_MANAGE)


def require(actor: Actor, *permissions: str) -> None:
    """403 unless the caller holds one of `permissions`."""
    if not permissions:
        raise ValueError("require() needs at least one permission")
    if not any(actor.can(p) for p in permissions):
        raise forbidden(f"missing permission {' or '.join(permissions)}")
