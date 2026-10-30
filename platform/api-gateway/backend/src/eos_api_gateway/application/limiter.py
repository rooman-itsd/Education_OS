"""Which buckets a request draws from, and whether it may pass. The store (in-process or Redis) holds the
buckets; the clock is injected so tests move time instead of sleeping."""

from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import jwt
from eos_core.security import decode_token

from ..domain.bucket import Limit, retry_after
from ..settings import GatewaySettings

log = logging.getLogger("eos.gateway")


class BucketStore(Protocol):
    def take(self, key: str, limit: Limit, now: float) -> float | None:
        """Take one token from the bucket at `key`. None when allowed, else the seconds until the next token."""


@dataclass(frozen=True)
class Denied:
    scope: str  # ip | organisation | auth
    retry_after: int  # whole seconds, for the Retry-After header


class RateLimiter:
    def __init__(self, settings: GatewaySettings, store: BucketStore, clock: Callable[[], float] = time.time):
        self.settings = settings
        self.store = store
        self.clock = clock
        self._trust_all = "*" in settings.trusted_proxies
        self._trusted = [ipaddress.ip_network(p, strict=False) for p in settings.trusted_proxies if p != "*"]

    @property
    def enabled(self) -> bool:
        return self.settings.rate_limit

    def is_trusted(self, peer: str | None) -> bool:
        if self._trust_all:
            return True
        try:
            address = ipaddress.ip_address(peer or "")
        except ValueError:
            return False  # not an IP (the test client, a unix socket): never a proxy we configured
        return any(address in net for net in self._trusted)

    def client_ip(self, peer: str | None, forwarded_for: str | None) -> str:
        """The address the buckets are keyed by. X-Forwarded-For counts only when the direct peer is a trusted
        proxy; the client is then the rightmost entry that is not itself a trusted proxy (each proxy appends
        the address it saw, so anything the client wrote stays to the left and is ignored)."""
        if not forwarded_for or not self.is_trusted(peer):
            return peer or "unknown"
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        for hop in reversed(hops):
            if not self.is_trusted(hop):
                return hop
        return hops[0] if hops else (peer or "unknown")

    @staticmethod
    def organisation(authorization: str | None) -> str | None:
        """The `org` claim of a valid bearer token; anything else (no token, expired, forged) is anonymous and
        draws from the IP bucket only. Verification is left to the routes."""
        if not authorization or not authorization.lower().startswith("bearer "):
            return None
        try:
            claims = decode_token(authorization.split(" ", 1)[1].strip())
        except jwt.PyJWTError:
            return None
        org = claims.get("org")
        return str(org) if org else None

    def check(
        self, *, path: str, peer: str | None, forwarded_for: str | None, authorization: str | None
    ) -> Denied | None:
        if not self.enabled or path in self.settings.exempt_paths:
            return None
        now = self.clock()
        ip = self.client_ip(peer, forwarded_for)
        checks: list[tuple[str, str, Limit]] = []
        if any(path.startswith(p) for p in self.settings.auth_paths):
            checks.append(("auth", f"auth:{ip}", self.settings.auth))
        checks.append(("ip", f"ip:{ip}", self.settings.ip))
        org = self.organisation(authorization)
        if org:
            checks.append(("organisation", f"org:{org}", self.settings.organisation))
        for scope, key, limit in checks:
            wait = self.store.take(key, limit, now)
            if wait is not None:
                log.info("rate limited scope=%s key=%s path=%s retry_after=%.1fs", scope, key, path, wait)
                return Denied(scope, retry_after(wait))
        return None
