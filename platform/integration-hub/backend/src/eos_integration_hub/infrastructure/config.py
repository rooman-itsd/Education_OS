"""Module-local configuration. Keys are INTEGRATION_HUB_*, documented in config/env.example. Read from the
environment on every call, so a test or a redeploy never sees a stale value. Every number is clamped to a sane
range, so a typo in the environment slows or speeds the hub, never breaks a timestamp calculation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

API_PREFIX = "/api/v1/integration-hub"


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


def _list(name: str) -> tuple[str, ...]:
    return tuple(p.strip().lower() for p in os.environ.get(name, "").split(",") if p.strip())


@dataclass(frozen=True)
class HubConfig:
    public_base_url: str
    secret_backend: str
    secret_dir: str
    secret_kek: str
    secret_kek_previous: str
    allow_mock: bool
    allowed_return_hosts: tuple[str, ...]
    oauth_state_ttl_s: int
    token_refresh_lead_s: int
    inbound_max_bytes: int
    provider_request_timeout_s: int
    inbound_raw_retention_days: int
    inbound_reject_limit_per_min: int
    inbound_rejected_retention_days: int
    sync_timeout_s: int
    idempotency_window_days: int
    retry_max_attempts: int
    retry_base_s: int
    retry_max_s: int
    queue_expiry_hours: int
    delivery_payload_retention_days: int
    delivery_log_retention_days: int
    health_interval_min: int
    health_runs_per_hour: int
    adapters: tuple[str, ...]

    @classmethod
    def from_env(cls) -> HubConfig:
        return cls(
            public_base_url=os.environ.get("INTEGRATION_HUB_PUBLIC_BASE_URL", "").strip().rstrip("/"),
            secret_backend=os.environ.get("INTEGRATION_HUB_SECRET_BACKEND", "file").strip().lower() or "file",
            secret_dir=os.environ.get("INTEGRATION_HUB_SECRET_DIR", "/var/lib/eos/integration-hub/secrets").strip(),
            secret_kek=os.environ.get("INTEGRATION_HUB_SECRET_KEK", "").strip(),
            secret_kek_previous=os.environ.get("INTEGRATION_HUB_SECRET_KEK_PREVIOUS", "").strip(),
            allow_mock=_bool("INTEGRATION_HUB_ALLOW_MOCK"),
            allowed_return_hosts=_list("INTEGRATION_HUB_ALLOWED_RETURN_HOSTS"),
            oauth_state_ttl_s=_int("INTEGRATION_HUB_OAUTH_STATE_TTL_S", 600, 60, 3600),
            token_refresh_lead_s=_int("INTEGRATION_HUB_TOKEN_REFRESH_LEAD_S", 600, 60, 86_400),
            inbound_max_bytes=_int("INTEGRATION_HUB_INBOUND_MAX_BYTES", 1_048_576, 1024, 10_485_760),
            provider_request_timeout_s=_int("INTEGRATION_HUB_PROVIDER_REQUEST_TIMEOUT_S", 10, 1, 60),
            inbound_raw_retention_days=_int("INTEGRATION_HUB_INBOUND_RAW_RETENTION_DAYS", 7, 0, 90),
            inbound_reject_limit_per_min=_int("INTEGRATION_HUB_INBOUND_REJECT_LIMIT_PER_MIN", 30, 1, 10_000),
            inbound_rejected_retention_days=_int("INTEGRATION_HUB_INBOUND_REJECTED_RETENTION_DAYS", 7, 1, 90),
            sync_timeout_s=_int("INTEGRATION_HUB_SYNC_TIMEOUT_S", 15, 1, 120),
            idempotency_window_days=_int("INTEGRATION_HUB_IDEMPOTENCY_WINDOW_DAYS", 30, 1, 400),
            retry_max_attempts=_int("INTEGRATION_HUB_RETRY_MAX_ATTEMPTS", 8, 1, 50),
            retry_base_s=_int("INTEGRATION_HUB_RETRY_BASE_S", 30, 1, 3600),
            retry_max_s=_int("INTEGRATION_HUB_RETRY_MAX_S", 21_600, 1, 86_400),
            queue_expiry_hours=_int("INTEGRATION_HUB_QUEUE_EXPIRY_HOURS", 72, 1, 24 * 30),
            delivery_payload_retention_days=_int("INTEGRATION_HUB_DELIVERY_PAYLOAD_RETENTION_DAYS", 30, 1, 400),
            delivery_log_retention_days=_int("INTEGRATION_HUB_DELIVERY_LOG_RETENTION_DAYS", 400, 30, 3650),
            health_interval_min=_int("INTEGRATION_HUB_HEALTH_INTERVAL_MIN", 15, 1, 1440),
            health_runs_per_hour=_int("INTEGRATION_HUB_HEALTH_RUNS_PER_HOUR", 12, 1, 600),
            adapters=_list("INTEGRATION_HUB_ADAPTERS"),
        )

    def public_url(self, path: str) -> str:
        """An absolute URL on the public base for a hub path (an inbound route or the OAuth callback). Without a
        base (development) the path alone is returned, which a provider cannot call but an admin can read."""
        return f"{self.public_base_url}{API_PREFIX}{path}"

    def return_host_allowed(self, url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return False
        if parts.scheme not in ("https", "http") or not parts.hostname:
            return False
        if parts.username or parts.password:
            return False
        host = parts.hostname.lower()
        if parts.scheme == "http" and host not in ("localhost", "127.0.0.1"):
            return False  # plain http only for a developer's own machine
        return host in self.allowed_return_hosts
