"""eos_core.oidc is only the verification primitive (ADR-0006): realm addressing, a cached JWKS, signature,
issuer, audience and expiry checks, and the hand-off to the host's resolver. No user lookup lives here."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from eos_core import oidc
from eos_core.security import create_token, decode_token
from eos_core.settings import settings

BASE = "https://edu.example/auth"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(oidc, "settings", replace(settings, oidc_issuer_base=BASE, oidc_realms="pilot, second"))
    monkeypatch.setattr(oidc.hooks, "resolve_claims", oidc.OIDCHooks().resolve_claims)
    oidc.jwks.clear()
    yield
    oidc.jwks.clear()


@pytest.fixture
def keys():
    rsa = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa", reason="PyJWT[crypto] needed for RS256")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    return private, {"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]}


def _token(private, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": f"{BASE}/realms/pilot",
        "aud": "education-os-web",
        "sub": "kc-1",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        **overrides,
    }
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": overrides.pop("kid", "k1")})


def test_realm_addressing(on):
    assert oidc.configured()
    assert oidc.issuer("pilot") == f"{BASE}/realms/pilot"
    assert oidc.realm_from_issuer(f"{BASE}/realms/pilot") == "pilot"
    assert oidc.realm_from_issuer(f"{BASE}/realms/pilot/extra") is None
    assert oidc.realm_from_issuer("https://other.example/auth/realms/pilot") is None
    assert oidc.realm_from_issuer(None) is None
    assert oidc.realm_exists("pilot") and oidc.realm_exists("second")
    assert not oidc.realm_exists("third") and not oidc.realm_exists("") and not oidc.realm_exists("Pilot!")
    e = oidc.endpoints("pilot")
    assert e["authorization_endpoint"].endswith("/realms/pilot/protocol/openid-connect/auth")
    assert e["jwks_uri"].endswith("/realms/pilot/protocol/openid-connect/certs")
    assert e["client_id"] == "education-os-web" and e["code_challenge_method"] == "S256"


def test_star_means_every_slug(monkeypatch):
    monkeypatch.setattr(oidc, "settings", replace(settings, oidc_issuer_base=BASE, oidc_realms="*"))
    assert oidc.realm_exists("anything-active")
    monkeypatch.setattr(oidc, "settings", replace(settings, oidc_issuer_base="", oidc_realms="*"))
    assert not oidc.configured() and not oidc.realm_exists("anything-active")


def test_verify_checks_signature_issuer_audience_and_expiry(on, keys, monkeypatch):
    private, doc = keys
    monkeypatch.setattr(oidc.jwks, "fetch", lambda url: doc)
    claims = oidc.verify_realm_token(_token(private))
    assert claims["sub"] == "kc-1" and claims["realm"] == "pilot"
    for bad in ({"iss": "https://evil.example/auth/realms/pilot"}, {"aud": "x"}, {"exp": 10}):
        with pytest.raises(jwt.PyJWTError):
            oidc.verify_realm_token(_token(private, **bad))
    with pytest.raises(oidc.OIDCError, match="unknown signing key"):
        oidc.verify_realm_token(_token(private, kid="k2"))
    with pytest.raises(jwt.PyJWTError):  # HS256 is never a realm token
        oidc.verify_realm_token(jwt.encode({"iss": f"{BASE}/realms/pilot"}, "secret", algorithm="HS256"))


def test_jwks_cache_ttl_and_refresh_on_unknown_kid(on, keys, monkeypatch):
    private, doc = keys
    calls = []

    def fetch(url):
        calls.append(url)
        return doc

    cache = oidc.JWKSCache(ttl_seconds=1000, fetch=fetch)
    monkeypatch.setattr(oidc, "jwks", cache)
    oidc.verify_realm_token(_token(private))
    oidc.verify_realm_token(_token(private))
    assert len(calls) == 1 and calls[0] == f"{BASE}/realms/pilot/protocol/openid-connect/certs"
    with pytest.raises(oidc.OIDCError):
        oidc.verify_realm_token(_token(private, kid="rotated"))
    assert len(calls) == 2  # one refresh for the unknown kid
    now = [1_000.0]
    monkeypatch.setattr(oidc.time, "monotonic", lambda: now[0])
    cache.clear()
    oidc.verify_realm_token(_token(private))
    now[0] += 2_000
    oidc.verify_realm_token(_token(private))
    assert len(calls) == 4  # expired entry fetched again


def test_fetch_failure_is_an_oidc_error(on, keys, monkeypatch):
    import httpx

    private, _ = keys

    def failing(url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(oidc.jwks, "fetch", failing)
    with pytest.raises(oidc.OIDCError, match="cannot fetch"):
        oidc.verify_realm_token(_token(private))


def test_decode_token_routes_by_algorithm(on, keys, monkeypatch):
    private, doc = keys
    monkeypatch.setattr(oidc.jwks, "fetch", lambda url: doc)
    own = create_token(user_id="u1", organisation_id="o1", roles=["student"])
    assert decode_token(own)["sub"] == "u1"  # the HS256 path is unchanged
    with pytest.raises(oidc.OIDCError, match="no resolver"):  # verified, but nobody can say which user
        decode_token(_token(private))
    monkeypatch.setattr(oidc.hooks, "resolve_claims", lambda c: {"sub": "user-" + c["sub"], "org": c["realm"]})
    assert decode_token(_token(private)) == {"sub": "user-kc-1", "org": "pilot"}
    with pytest.raises(jwt.PyJWTError):
        decode_token("not-a-token")


def test_not_configured_refuses_realm_tokens(keys, monkeypatch):
    private, _ = keys
    monkeypatch.setattr(oidc, "settings", replace(settings, oidc_issuer_base=""))
    with pytest.raises(oidc.OIDCNotConfiguredError):
        oidc.verify_realm_token(_token(private))


def test_exchange_code_posts_pkce_to_the_token_endpoint(on, monkeypatch):
    import httpx

    seen = {}

    def post(url, *, data, timeout):
        seen.update(url=url, data=data, timeout=timeout)
        return httpx.Response(200, json={"id_token": "x"})

    monkeypatch.setattr(oidc.httpx, "post", post)
    assert oidc.exchange_code("pilot", code="c", code_verifier="v", redirect_uri="https://app/") == {"id_token": "x"}
    assert seen["url"] == f"{BASE}/realms/pilot/protocol/openid-connect/token"
    assert seen["data"] == {
        "grant_type": "authorization_code",
        "client_id": "education-os-web",
        "code": "c",
        "redirect_uri": "https://app/",
        "code_verifier": "v",
    }
    monkeypatch.setattr(oidc.httpx, "post", lambda url, **kw: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(oidc.OIDCError, match="invalid_grant"):
        oidc.exchange_code("pilot", code="c", code_verifier="v", redirect_uri="https://app/")


def test_exchange_code_unreachable_realm_is_a_refusal(on, monkeypatch):
    import httpx

    def down(url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(oidc.httpx, "post", down)
    with pytest.raises(oidc.OIDCError, match="cannot reach"):
        oidc.exchange_code("pilot", code="c", code_verifier="v", redirect_uri="https://app/")
