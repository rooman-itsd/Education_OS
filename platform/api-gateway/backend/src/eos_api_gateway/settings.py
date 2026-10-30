"""Configuration of the gateway middlewares. apps/backend reads it from the environment once per create_app();
tests pass a GatewaySettings. Every key is documented in config/env.example."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .domain.bucket import Limit

# Peers whose X-Forwarded-For is believed by default: loopback only. Trusting whole private ranges would let any
# client on the office LAN or VPN write its own X-Forwarded-For and pick a fresh bucket per request, so a
# deployment names its reverse proxy: EOS_TRUSTED_PROXIES=<the nginx container's address> (infra/docker/
# .env.api.example; tools/scripts/deploy-api-lxc.sh writes it). The list replaces this default; "*" makes every
# direct peer a proxy (only behind a proxy that is the sole way in).
DEFAULT_TRUSTED_PROXIES = ("127.0.0.0/8", "::1/128")

# Paths a token bucket never touches. Monitoring polls health; a limiter in front of it would hide an outage.
DEFAULT_EXEMPT_PATHS = ("/api/v1/health",)

# Sign-in and sign-up: the stricter bucket, per client IP, against password guessing and bulk registrations.
# The anonymous public routes of every module (/api/v1/<module>/public/..., e.g. admissions' application
# form) draw from the same bucket: they are the other thing a stranger can call without a token.
DEFAULT_AUTH_PATHS = ("/api/v1/identity/auth/login", "/api/v1/tenancy/register")
PUBLIC_SEGMENT = "public"

# Sign-in, per account (the email in the body) on top of the per-address bucket: a lab of 40 behind one NAT
# address signs in together, while nobody gets more than a handful of guesses at one account.
DEFAULT_LOGIN_PATHS = ("/api/v1/identity/auth/login",)


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
    """Defaults sized for a school: one campus is often one NAT address, and a class signs in at once.
    Signed-in requests are charged to their organisation only, so the IP bucket meters anonymous traffic.
    The reasoning is in README.md (Sizing the limits)."""

    security_headers: bool = True
    hsts_max_age: int = 31_536_000  # one year, the usual value for a host that is HTTPS-only
    rate_limit: bool = True
    ip: Limit = Limit(1200, 1200)
    organisation: Limit = Limit(3000, 3000)
    auth: Limit = Limit(60, 60)
    login: Limit = Limit(10, 10)
    trusted_proxies: tuple[str, ...] = DEFAULT_TRUSTED_PROXIES
    exempt_paths: tuple[str, ...] = DEFAULT_EXEMPT_PATHS
    auth_paths: tuple[str, ...] = DEFAULT_AUTH_PATHS
    login_paths: tuple[str, ...] = DEFAULT_LOGIN_PATHS
    redis_url: str | None = None

    @property
    def proxies_unset(self) -> bool:
        """True while `trusted_proxies` is still the loopback default (the variable is unset, empty, or the
        compose file's own default filled in): behind a reverse proxy every anonymous request then keys on the
        proxy's address."""
        return self.trusted_proxies == DEFAULT_TRUSTED_PROXIES

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
            login=_limit(env, "LOGIN", cls.login.per_minute),
            trusted_proxies=_csv(env.get("EOS_TRUSTED_PROXIES"), DEFAULT_TRUSTED_PROXIES),
            redis_url=(env.get("EOS_REDIS_URL") or "").strip() or None,
        )
