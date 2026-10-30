"""OpenID Connect verification primitive (ADR-0006): Keycloak RS256 tokens, one realm per organisation.

This module only speaks to the provider and checks signatures. It knows nothing about users: the host
registers `hooks.resolve_claims` (platform/identity implements it) to turn a verified realm token into the
platform's own claim shape (`sub` = identity user id, `org`, `roles`). eos_core must not import identity.

Realm issuers are `<EOS_OIDC_ISSUER_BASE>/realms/<slug>`; the realm's JWKS is fetched over HTTPS, cached per
realm for a TTL, and refreshed once when a token names a key id the cache does not hold.
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
    r = httpx.get(url, timeout=settings.oidc_http_timeout)
    r.raise_for_status()
    return r.json()


@dataclass
class _Entry:
    keys: dict[str, object]
    fetched_at: float


@dataclass
class JWKSCache:
    ttl_seconds: float = field(default_factory=lambda: settings.oidc_jwks_ttl_seconds)
    fetch: Callable[[str], dict] = field(default_factory=lambda: fetch_jwks)
    _entries: dict[str, _Entry] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _load(self, realm: str) -> _Entry:
        try:
            doc = self.fetch(endpoints(realm)["jwks_uri"])
        except (httpx.HTTPError, ValueError) as e:
            raise OIDCError(f"cannot fetch the signing keys of realm {realm}: {e}") from e
        keys: dict[str, object] = {}
        for k in doc.get("keys") or []:
            if k.get("kty") == "RSA" and k.get("kid") and k.get("use", "sig") == "sig":
                try:
                    keys[k["kid"]] = jwt.PyJWK(k, algorithm="RS256").key
                except jwt.PyJWTError:
                    continue
        entry = _Entry(keys=keys, fetched_at=time.monotonic())
        self._entries[realm] = entry
        return entry

    def signing_key(self, realm: str, kid: str) -> object:
        """The public key `kid` of `realm`: from the cache while fresh, else fetched; an unknown kid refreshes
        once (key rotation), then fails."""
        with self._lock:
            entry = self._entries.get(realm)
            if entry is None or time.monotonic() - entry.fetched_at > self.ttl_seconds or kid not in entry.keys:
                entry = self._load(realm)
            key = entry.keys.get(kid)
        if key is None:
            raise OIDCError(f"unknown signing key {kid!r} for realm {realm}")
        return key

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


jwks = JWKSCache()


# ---- verification ------------------------------------------------------------------------------------


def verify_realm_token(token: str) -> dict:
    """Verify an RS256 token from one of our realms: signature against the realm's JWKS, issuer, audience
    (EOS_OIDC_CLIENT_ID) and expiry. Returns the raw claims plus `realm`. Nothing here resolves a user."""
    if not configured():
        raise OIDCNotConfiguredError("OIDC is not configured on this API")
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256":
        raise OIDCError(f"unsupported algorithm {header.get('alg')!r}")
    unverified = jwt.decode(token, options={"verify_signature": False})
    realm = realm_from_issuer(unverified.get("iss"))
    if realm is None:
        raise OIDCError("issuer is not a realm of this platform")
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
    return {**claims, "realm": realm}


def decode_realm_token(token: str) -> dict:
    """Verify, then hand the claims to the host's resolver for the platform shape."""
    return hooks.resolve_claims(verify_realm_token(token))


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
