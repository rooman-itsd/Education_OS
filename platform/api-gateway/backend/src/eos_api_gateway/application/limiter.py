"""Which buckets a request draws from, and whether it may pass. The store (in-process or Redis) holds the
buckets; the clock is injected so tests move time instead of sleeping."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import jwt
from eos_core.security import decode_token

from ..domain.bucket import Limit, retry_after
from ..settings import PUBLIC_SEGMENT, GatewaySettings

log = logging.getLogger("eos.gateway")


class BucketStore(Protocol):
    def take(self, key: str, limit: Limit, now: float) -> float | None:
        """Take one token from the bucket at `key`. None when allowed, else the seconds until the next token."""


@dataclass(frozen=True)
class Denied:
    scope: str  # ip | organisation | auth | login
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
        """The address the anonymous buckets are keyed by. X-Forwarded-For counts only when the direct peer is a
        trusted proxy. Each proxy appends the address it saw, so the chain is read from the right: the client is
        the first hop that is not itself a trusted proxy, and anything the client wrote stays to its left,
        unread. When every hop is a trusted proxy (or every peer is, with "*"), the rightmost hop is used: a
        proxy wrote it, so it is never a value the client picked."""
        if not forwarded_for or not self.is_trusted(peer):
            return peer or "unknown"
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        if not hops:
            return peer or "unknown"
        if self._trust_all:
            return hops[-1]
        for hop in reversed(hops):
            if not self.is_trusted(hop):
                return hop
        return hops[-1]

    @staticmethod
    def organisation(authorization: str | None) -> str | None:
        """The `org` claim of a valid bearer token; anything else (no token, expired, forged, a platform token
        without an organisation) is anonymous and draws from the IP bucket. Authorisation is left to the
        routes."""
        if not authorization or not authorization.lower().startswith("bearer "):
            return None
        try:
            claims = decode_token(authorization.split(" ", 1)[1].strip())
        except jwt.PyJWTError:
            return None
        org = claims.get("org")
        return str(org) if org else None

    def is_auth_path(self, path: str) -> bool:
        """Sign-in, sign-up and every module's anonymous /api/v1/<module>/public/... routes."""
        if any(path.startswith(p) for p in self.settings.auth_paths):
            return True
        parts = path.split("/")
        return len(parts) > 5 and parts[1:3] == ["api", "v1"] and parts[4] == PUBLIC_SEGMENT

    def is_login_path(self, path: str) -> bool:
        return path in self.settings.login_paths

    def check(
        self,
        *,
        path: str,
        peer: str | None,
        forwarded_for: str | None,
        authorization: str | None,
        login_email: str | None = None,
    ) -> Denied | None:
        """Which buckets the request draws from:
        - sign-in, sign-up and public routes: the auth bucket of the client address, and on sign-in also the
          bucket of the account (`login_email`, from the body);
        - a valid token with an organisation: that organisation's bucket only. Its users behind one campus
          NAT address do not use up the address's bucket, and the organisation's bucket bounds them instead;
        - anything else (no token, an invalid one, a platform token): the client address's bucket."""
        if not self.enabled or path in self.settings.exempt_paths:
            return None
        now = self.clock()
        checks: list[tuple[str, str, Limit]] = []
        if self.is_auth_path(path):
            ip = self.client_ip(peer, forwarded_for)
            checks.append(("auth", f"auth:{ip}", self.settings.auth))
            if login_email and self.is_login_path(path):
                checks.append(("login", f"login:{_account_key(login_email)}", self.settings.login))
        org = self.organisation(authorization)
        if org:
            checks.append(("organisation", f"org:{org}", self.settings.organisation))
        else:
            checks.append(("ip", f"ip:{self.client_ip(peer, forwarded_for)}", self.settings.ip))
        for scope, key, limit in checks:
            wait = self.store.take(key, limit, now)
            if wait is not None:
                log.info("rate limited scope=%s key=%s path=%s retry_after=%.1fs", scope, key, path, wait)
                return Denied(scope, retry_after(wait))
        return None


def _account_key(email: str) -> str:
    """The per-account bucket's key: a digest of the normalised email, so neither the store nor the log line
    holds the address itself."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:32]
