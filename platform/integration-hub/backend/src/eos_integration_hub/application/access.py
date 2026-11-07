"""The permission keys of contracts/permissions.yaml. Routes name them through eos_identity's require()."""

from __future__ import annotations

ADAPTER_READ = "integration-hub:adapter:read"
CONNECTION_READ = "integration-hub:connection:read"
CONNECTION_MANAGE = "integration-hub:connection:manage"
CONNECTION_GO_LIVE = "integration-hub:connection:go-live"
DELIVERY_READ = "integration-hub:delivery:read"
DELIVERY_RETRY = "integration-hub:delivery:retry"
ACCOUNT_LINK_READ = "integration-hub:account-link:read"
ACCOUNT_LINK_REVOKE = "integration-hub:account-link:revoke"
SELF_LINK = "integration-hub:self:link"
PLATFORM_ADMIN = "platform:integration-hub:admin"

PERMISSION_KEYS = (
    ADAPTER_READ,
    CONNECTION_READ,
    CONNECTION_MANAGE,
    CONNECTION_GO_LIVE,
    DELIVERY_READ,
    DELIVERY_RETRY,
    ACCOUNT_LINK_READ,
    ACCOUNT_LINK_REVOKE,
    SELF_LINK,
    PLATFORM_ADMIN,
)
