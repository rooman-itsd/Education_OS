"""OpenID Connect verification primitive (ADR-0006): Keycloak RS256 tokens, one realm per organisation.

This module only speaks to the provider and checks signatures. It knows nothing about users: the host
registers `hooks.resolve_claims` (platform/identity implements it) to turn a verified realm token into the
platform's own claim shape (`sub` = identity user id, `org`, `roles`). eos_core must not import identity.

Realm issuers are `<EOS_OIDC_ISSUER_BASE>/realms/<slug>`; the realm's JWKS is fetched over HTTPS, cached per
realm for a TTL, and refreshed when a token names a key id the cache does not hold (key rotation).

The realm is read from the token's unverified `iss`, so everything before the signature check assumes the token
is forged: a realm that is not configured (EOS_OIDC_REALMS) is refused before any network call, the fetch runs
outside the cache lock with a short timeout, an unknown key id refetches at most once per realm per window, a
failed fetch is remembered for a while, and only a few fetches run at once across all realms. A flood of forged
tokens therefore costs a bounded number of requests to Keycloak and never holds the API's worker threads.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import jwt

from .settings import settings

_REALM_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class OIDCError(jwt.InvalidTokenError):
    """A realm token that cannot be accepted. Subclasses PyJWT's error so callers that already map
    `jwt.PyJWTError` to 401 need no change."""


class OIDCNotConfiguredError(OIDCError):
    """EOS_OIDC_ISSUER_BASE is empty, or the slug has no realm."""


class OIDCHooks:
    """Filled by the host at startup (apps/backend wires platform/identity). The default refuses every realm
    token: without a resolver no `sub` could name an identity user."""

    def resolve_claims(self, claims: dict) -> dict:  # noqa: ARG002
        raise OIDCError("no resolver registered for OIDC tokens")


hooks = OIDCHooks()


# ---- realm addressing -------------------------------------------------------------------------------


def configured() -> bool:
    return bool(settings.oidc_issuer_base)


def realm_exists(slug: str) -> bool:
    """Whether `slug` has a realm, per EOS_OIDC_REALMS (`*`: every organisation; else a list of slugs)."""
    if not configured() or not slug or not _REALM_NAME.match(slug):
        return False
    realms = settings.oidc_realms.strip()
    if realms == "*":
        return True
    return slug in {r.strip() for r in realms.split(",") if r.strip()}


def issuer(realm: str) -> str:
    return f"{settings.oidc_issuer_base}/realms/{realm}"


def realm_from_issuer(iss: str | None) -> str | None:
    """The realm an issuer names, or None when it is not one of ours."""
    if not configured() or not isinstance(iss, str):
        return None
    prefix = f"{settings.oidc_issuer_base}/realms/"
    if not iss.startswith(prefix):
        return None
    realm = iss[len(prefix) :]
    return realm if _REALM_NAME.match(realm) else None


def endpoints(realm: str) -> dict:
    """Keycloak's fixed endpoint layout under the realm issuer, plus what the web shell needs for PKCE."""
    base = issuer(realm)
    return {
        "realm": realm,
        "issuer": base,
        "authorization_endpoint": f"{base}/protocol/openid-connect/auth",
        "token_endpoint": f"{base}/protocol/openid-connect/token",
        "jwks_uri": f"{base}/protocol/openid-connect/certs",
        "end_session_endpoint": f"{base}/protocol/openid-connect/logout",
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "code_challenge_method": "S256",
    }


# ---- JWKS cache --------------------------------------------------------------------------------------


def fetch_jwks(url: str) -> dict:
    """GET the JWKS document. Tests replace this to serve a key pair of their own."""
    r = httpx.get(url, timeout=settings.oidc_jwks_timeout)
    r.raise_for_status()
    return r.json()


def _parse_keys(doc: object) -> dict[str, object]:
    keys: dict[str, object] = {}
    for k in (doc.get("keys") if isinstance(doc, dict) else None) or []:
        if isinstance(k, dict) and k.get("kty") == "RSA" and k.get("kid") and k.get("use", "sig") == "sig":
            try:
                keys[k["kid"]] = jwt.PyJWK(k, algorithm="RS256").key
            except jwt.PyJWTError:
                continue
    return keys


@dataclass
class _Realm:
    keys: dict[str, object] = field(default_factory=dict)
    fetched_at: float | None = None  # last successful fetch
    refetched_at: float | None = None  # last fetch made because of an unknown key id
    failed_at: float | None = None  # last failed fetch, and why
    error: str = ""
    inflight: threading.Event | None = None  # set while one thread fetches this realm's keys


@dataclass
class JWKSCache:
    """Signing keys per realm. The lock guards only the cache: network calls happen outside it."""

    ttl_seconds: float = field(default_factory=lambda: settings.oidc_jwks_ttl_seconds)
    fetch: Callable[[str], dict] = field(default_factory=lambda: fetch_jwks)
    refetch_interval_seconds: float = 60.0  # at most one unknown-kid refetch per realm per window
    failure_ttl_seconds: float = 30.0  # a failed fetch is answered from memory for this long
    max_concurrent_fetches: int = 4  # across all realms; beyond it a request is refused, not queued
    max_realms: int = 1024  # entries kept; failed and oldest ones go first
    _realms: dict[str, _Realm] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _fetching: int = 0

    def signing_key(self, realm: str, kid: str) -> object:
        """The public key `kid` of `realm`: from the cache while fresh, else fetched. An unknown kid refetches
        (key rotation) at most once per realm per `refetch_interval_seconds`, then fails from the cache."""
        for _ in range(2):  # a second pass only after waiting for another thread's fetch of the same realm
            with self._lock:
                st = self._realms.get(realm)
                if st is None:
                    self._evict()
                    st = self._realms[realm] = _Realm()
                now = time.monotonic()
                fresh = st.fetched_at is not None and now - st.fetched_at <= self.ttl_seconds
                if fresh and kid in st.keys:
                    return st.keys[kid]
                if st.inflight is not None:
                    waiting = st.inflight
                else:
                    waiting = None
                    if st.failed_at is not None and now - st.failed_at < self.failure_ttl_seconds:
                        raise OIDCError(st.error)
                    if fresh and st.refetched_at is not None and now - st.refetched_at < self.refetch_interval_seconds:
                        raise OIDCError(f"unknown signing key {kid!r} for realm {realm}")
                    if self._fetching >= self.max_concurrent_fetches:
                        raise OIDCError("too many signing-key fetches in progress; try again")
                    self._fetching += 1
                    st.inflight = threading.Event()
                    if fresh:
                        st.refetched_at = now
            if waiting is not None:
                waiting.wait(settings.oidc_jwks_timeout + 1)
                continue
            return self._fetch_into(realm, st, kid)
        raise OIDCError(f"signing keys of realm {realm} are still being fetched; try again")

    def _fetch_into(self, realm: str, st: _Realm, kid: str) -> object:
        """Fetch outside the lock, then publish the result (keys, or the failure) under it."""
        keys: dict[str, object] | None = None
        error = f"cannot fetch the signing keys of realm {realm}"
        try:
            keys = _parse_keys(self.fetch(endpoints(realm)["jwks_uri"]))
        except (httpx.HTTPError, ValueError, OSError) as e:
            error = f"{error}: {e}"
        finally:  # whatever happened, release the slot and wake the waiters
            with self._lock:
                self._fetching -= 1
                now = time.monotonic()
                if keys is None:
                    st.failed_at, st.error = now, error
                else:
                    st.keys, st.fetched_at, st.failed_at, st.error = keys, now, None, ""
                event, st.inflight = st.inflight, None
            if event is not None:
                event.set()
        if keys is None:
            raise OIDCError(error)
        key = keys.get(kid)
        if key is None:
            raise OIDCError(f"unknown signing key {kid!r} for realm {realm}")
        return key

    def _evict(self) -> None:
        """Keep at most `max_realms` entries (with `*`, any slug-shaped issuer gets one): failed entries
        first, then the least recently fetched. Called with the lock held."""
        if len(self._realms) < self.max_realms:
            return
        idle = [(r, st) for r, st in self._realms.items() if st.inflight is None]
        idle.sort(key=lambda item: (bool(item[1].keys), item[1].fetched_at or 0.0))
        for r, _ in idle[: max(1, len(self._realms) - self.max_realms + 1)]:
            del self._realms[r]

    def clear(self) -> None:
        with self._lock:
            self._realms.clear()


jwks = JWKSCache()


# ---- verification ------------------------------------------------------------------------------------

ACCESS_TOKEN = "Bearer"  # Keycloak's `typ` for an access token
ID_TOKEN = "ID"  # and for an ID token


def verify_realm_token(token: str, *, token_type: str = ACCESS_TOKEN) -> dict:
    """Verify an RS256 token from one of our realms: the realm is configured (EOS_OIDC_REALMS), then signature
    against the realm's JWKS, issuer, audience (EOS_OIDC_CLIENT_ID), expiry, Keycloak's `typ` (an access token
    by default, so an ID token cannot be used as a bearer token; the code callback asks for `ID`) and, when
    present, `azp` (the token was issued to our client). Returns the raw claims plus `realm`. Nothing here
    resolves a user."""
    if not configured():
        raise OIDCNotConfiguredError("OIDC is not configured on this API")
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256":
        raise OIDCError(f"unsupported algorithm {header.get('alg')!r}")
    unverified = jwt.decode(token, options={"verify_signature": False})
    realm = realm_from_issuer(unverified.get("iss"))
    if realm is None:
        raise OIDCError("issuer is not a realm of this platform")
    # Before any network call: the issuer is still unverified, and a realm taken out of EOS_OIDC_REALMS must
    # stop authenticating at once.
    if not realm_exists(realm):
        raise OIDCError(f"realm {realm} is not enabled on this platform")
    kid = header.get("kid")
    if not kid:
        raise OIDCError("token names no key id")
    key = jwks.signing_key(realm, kid)
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.oidc_client_id,
        issuer=issuer(realm),
        options={"require": ["exp", "iat", "sub"]},
    )
    if claims.get("typ") != token_type:
        raise OIDCError(f"expected a {token_type!r} token, got {claims.get('typ')!r}")
    if "azp" in claims and claims["azp"] != settings.oidc_client_id:
        raise OIDCError("token was issued to another client")
    return {**claims, "realm": realm}


def decode_realm_token(token: str) -> dict:
    """Verify an access token presented as a bearer token, then hand the claims to the host's resolver for the
    platform shape."""
    return hooks.resolve_claims(verify_realm_token(token, token_type=ACCESS_TOKEN))


# ---- authorization code exchange ---------------------------------------------------------------------


def exchange_code(realm: str, *, code: str, code_verifier: str, redirect_uri: str) -> dict:
    """Redeem an authorization code at the realm's token endpoint (public client with PKCE: no secret).
    Returns the token response; the caller verifies `id_token` with `verify_realm_token`. Tests replace this."""
    try:
        r = httpx.post(
            endpoints(realm)["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": settings.oidc_client_id,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            timeout=settings.oidc_http_timeout,
        )
    except httpx.HTTPError as e:  # Keycloak down or unreachable: a refused sign-in, not a 500
        raise OIDCError(f"cannot reach the token endpoint of realm {realm}: {e}") from e
    if r.status_code != 200:
        detail = ""
        try:
            detail = r.json().get("error_description") or r.json().get("error") or ""
        except ValueError:
            pass
        raise OIDCError(f"code exchange refused by realm {realm}: {detail or r.status_code}")
    try:
        return r.json()
    except ValueError as e:
        raise OIDCError(f"the token endpoint of realm {realm} answered no JSON") from e
