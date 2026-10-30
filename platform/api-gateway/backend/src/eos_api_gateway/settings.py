"""Configuration of the gateway middlewares. apps/backend reads it from the environment once per create_app();
tests pass a GatewaySettings. Every key is documented in config/env.example."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .domain.bucket import Limit

# Peers whose X-Forwarded-For is believed by default: the reverse proxy sits on the same host or the same
# private network (infra/docker/nginx.public-vhost.conf proxies from CT 101 to the API host over the LAN).
# EOS_TRUSTED_PROXIES replaces the list; "*" trusts every peer.
DEFAULT_TRUSTED_PROXIES = ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")

# Paths a token bucket never touches. Monitoring polls health; a limiter in front of it would hide an outage.
DEFAULT_EXEMPT_PATHS = ("/api/v1/health",)

# Sign-in and sign-up: the stricter bucket, per client IP, against password guessing and bulk registrations.
DEFAULT_AUTH_PATHS = ("/api/v1/identity/auth/login", "/api/v1/tenancy/register")


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    return default if raw is None or not raw.strip() else raw.strip().lower() in ("1", "true", "yes", "on")


def _int(env: Mapping[str, str], key: str, default: int | None) -> int | None:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"{key} must be a whole number, not {raw!r}") from e


def _limit(env: Mapping[str, str], name: str, per_minute: int, burst: int | None = None) -> Limit:
    rate = _int(env, f"EOS_RATE_LIMIT_{name}_PER_MINUTE", per_minute)
    b = _int(env, f"EOS_RATE_LIMIT_{name}_BURST", burst)
    try:
        return Limit.of(rate, b)
    except ValueError as e:
        raise RuntimeError(f"EOS_RATE_LIMIT_{name}_PER_MINUTE and _BURST must be positive") from e


def _csv(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return default
    return tuple(p.strip() for p in raw.split(",") if p.strip())


@dataclass(frozen=True)
class GatewaySettings:
    security_headers: bool = True
    hsts_max_age: int = 31_536_000  # one year, the usual value for a host that is HTTPS-only
    rate_limit: bool = True
    ip: Limit = Limit(600, 600)
    organisation: Limit = Limit(3000, 3000)
    auth: Limit = Limit(20, 20)
    trusted_proxies: tuple[str, ...] = DEFAULT_TRUSTED_PROXIES
    exempt_paths: tuple[str, ...] = DEFAULT_EXEMPT_PATHS
    auth_paths: tuple[str, ...] = DEFAULT_AUTH_PATHS
    redis_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> GatewaySettings:
        env = os.environ if env is None else env
        return cls(
            security_headers=_bool(env, "EOS_SECURITY_HEADERS", True),
            hsts_max_age=_int(env, "EOS_HSTS_MAX_AGE", cls.hsts_max_age),
            rate_limit=_bool(env, "EOS_RATE_LIMIT_ENABLED", True),
            ip=_limit(env, "IP", cls.ip.per_minute),
            organisation=_limit(env, "ORG", cls.organisation.per_minute),
            auth=_limit(env, "AUTH", cls.auth.per_minute),
            trusted_proxies=_csv(env.get("EOS_TRUSTED_PROXIES"), DEFAULT_TRUSTED_PROXIES),
            redis_url=(env.get("EOS_REDIS_URL") or "").strip() or None,
        )
