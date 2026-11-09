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

from ..domain.bucket import Limit, retry_after
from ..settings import PUBLIC_SEGMENT, GatewaySettings

log = logging.getLogger("eos.gateway")

# An IPv6 client usually holds a whole /64 (SLAAC, privacy addresses) and can pick a fresh address in it for
# every request; keyed per address it would get fresh buckets each time. So IPv6 is keyed by its /64.
IPV6_PREFIX = 64


class BucketStore(Protocol):
    async def take(self, key: str, limit: Limit, now: float) -> float | None:
        """Take one token from the bucket at `key`. None when allowed, else the seconds until the next token."""

    async def refund(self, key: str, limit: Limit, now: float) -> None:
        """Give back a token `take` charged for a request that should not have counted."""


@dataclass(frozen=True)
class Denied:
    scope: str  # ip | user | organisation | auth | login
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

    def client_key(self, peer: str | None, forwarded_for: str | None) -> str:
        """What the per-address buckets are keyed by: the client address, or its /64 for IPv6 (an IPv4-mapped
        IPv6 address is its IPv4 address). Anything that is not an address (the test client) is kept as is."""
        ip = self.client_ip(peer, forwarded_for)
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return ip
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped is not None:
                return str(address.ipv4_mapped)
            return str(ipaddress.IPv6Network((address, IPV6_PREFIX), strict=False))
        return ip

    @staticmethod
    def principal(claims: dict | None) -> tuple[str | None, str | None]:
        """(organisation, user) of a valid token's claims (`org`, `sub`). No claims (no token, an invalid one) or
        a platform token without an organisation is (None, ...) and draws from the address bucket.
        Authorisation is left to the routes."""
        if not claims:
            return None, None
        org, sub = claims.get("org"), claims.get("sub")
        return (str(org) if org else None), (str(sub) if sub else None)

    def is_auth_path(self, path: str) -> bool:
        """Sign-in, sign-up and every module's anonymous /api/v1/<module>/public/... routes."""
        if any(path.startswith(p) for p in self.settings.auth_paths):
            return True
        parts = path.split("/")
        return len(parts) > 5 and parts[1:3] == ["api", "v1"] and parts[4] == PUBLIC_SEGMENT

    def is_bounded_body_path(self, path: str) -> bool:
        """Sign-in and sign-up (the configured auth paths, not the modules' public routes, whose forms may be
        larger): their body is read by the gateway, at most 16 KiB of it, and a larger one is refused."""
        return any(path.startswith(p) for p in self.settings.auth_paths)

    def is_login_path(self, path: str) -> bool:
        return path in self.settings.login_paths

    def login_key(self, ip: str, email: str) -> str:
        """The per-account bucket's key: the account and the address it is tried from. Keyed on both, someone
        guessing from one address runs out of attempts there and cannot lock the account's owner out from
        another; guessing from many addresses is what the per-address auth bucket and the proxy are for."""
        return f"login:{_account_key(email)}:{ip}"

    async def refund_login(self, *, peer: str | None, forwarded_for: str | None, email: str) -> None:
        """Give back the attempt a sign-in was charged once it is known not to have been a failed one."""
        key = self.login_key(self.client_key(peer, forwarded_for), email)
        await self.store.refund(key, self.settings.login, self.clock())

    async def check(
        self,
        *,
        path: str,
        peer: str | None,
        forwarded_for: str | None,
        claims: dict | None,
        login_email: str | None = None,
    ) -> Denied | None:
        """Which buckets the request draws from, in this order:
        - sign-in, sign-up and public routes: the auth bucket of the client address, and on sign-in also the
          bucket of that account from that address (`login_email`, from the body; see `login_key`);
        - a valid token with an organisation (`claims`, decoded once per request by the middleware): the
          user's own bucket (`sub`), then the organisation's. The user's bucket keeps one client (a script, a
          stuck page) from emptying the organisation's for everyone else; the organisation's is the ceiling
          for all its users together. Neither is the address's: a campus behind one NAT address does not
          use up that address;
        - anything else (no token, an invalid one, a platform token): the client address's bucket.
        A request one bucket refuses is given back to the buckets it was already charged to: it never ran."""
        if not self.enabled or path in self.settings.exempt_paths:
            return None
        now = self.clock()
        checks: list[tuple[str, str, Limit]] = []
        address = self.client_key(peer, forwarded_for)
        if self.is_auth_path(path):
            checks.append(("auth", f"auth:{address}", self.settings.auth))
            if login_email and self.is_login_path(path):
                checks.append(("login", self.login_key(address, login_email), self.settings.login))
        org, user = self.principal(claims)
        if org:
            if user:
                checks.append(("user", f"user:{org}:{user}", self.settings.user))
            checks.append(("organisation", f"org:{org}", self.settings.organisation))
        else:
            checks.append(("ip", f"ip:{address}", self.settings.ip))
        taken: list[tuple[str, Limit]] = []
        for scope, key, limit in checks:
            wait = await self.store.take(key, limit, now)
            if wait is not None:
                for charged, charged_limit in taken:
                    await self.store.refund(charged, charged_limit, now)
                log.info("rate limited scope=%s key=%s path=%s retry_after=%.1fs", scope, key, path, wait)
                return Denied(scope, retry_after(wait))
            taken.append((key, limit))
        return None


def _account_key(email: str) -> str:
    """The per-account bucket's key: a digest of the normalised email, so neither the store nor the log line
    holds the address itself."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:32]
