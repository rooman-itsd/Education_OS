"""A fake Keycloak realm for identity's tests (ADR-0006): an RSA key pair generated here, the JWKS document
eos_core.oidc would fetch, and a token factory. Its own module (not conftest) so the test file can import it by
a unique name whichever suites share the pytest run."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

ISSUER_BASE = "https://edu.example/auth"
CLIENT_ID = "education-os-web"
# slug -> (organisation id, status). `pilot` has a realm (EOS_OIDC_REALMS); `norealm` is active but has none.
ORGS = {
    "pilot": ("org-pilot", "active"),
    "dormant": ("org-dormant", "suspended"),
    "gone": ("org-gone", "archived"),
    "norealm": ("org-norealm", "active"),
}


class Realm:
    """A fake Keycloak realm: an RSA key pair, a JWKS document and a token factory."""

    def __init__(self, kid: str = "pilot-key-1"):
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.kid = kid
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key(), as_dict=True)
        self.jwks = {"keys": [{**jwk, "kid": kid, "use": "sig", "alg": "RS256"}]}
        self.fetches = 0

    def fetch(self, url: str) -> dict:
        assert url.startswith(ISSUER_BASE + "/realms/"), url
        self.fetches += 1
        return self.jwks

    def token(self, realm: str = "pilot", *, kid: str | None = None, **overrides) -> str:
        now = datetime.now(UTC)
        claims = {
            "iss": f"{ISSUER_BASE}/realms/{realm}",
            "aud": CLIENT_ID,
            "sub": "kc-subject-1",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "email": "pilot.user@pilot.example.com",
            "email_verified": True,
            "typ": "Bearer",  # Keycloak's access token; its ID token says "ID"
            "azp": CLIENT_ID,
            **overrides,
        }
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.private, algorithm="RS256", headers={"kid": kid or self.kid})
