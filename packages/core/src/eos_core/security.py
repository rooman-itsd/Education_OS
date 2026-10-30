from __future__ import annotations

import hashlib
import hmac
import os
from datetime import timedelta

import jwt

from .db import utcnow
from .settings import settings

_ITER = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(calc.hex(), digest)
    except ValueError:
        return False


def create_token(
    *,
    user_id: str,
    organisation_id: str | None,
    roles: list[str],
    super_admin: bool = False,
    impersonated_by: str | None = None,
    ttl_minutes: int | None = None,
) -> str:
    now = utcnow()
    payload = {
        "sub": user_id,
        "org": organisation_id,
        "roles": roles,
        "sa": super_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes or settings.jwt_ttl_minutes)).timestamp()),
    }
    if impersonated_by:
        payload["imp"] = impersonated_by
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Claims of a token the API accepts: its own HS256 tokens, or (ADR-0006) an RS256 token from one of our
    Keycloak realms, verified against the realm's JWKS and handed to the host's resolver so the claims come back
    in the same shape (`sub` an identity user id, `org`, `roles`). The algorithm picks the path, so an HS256
    token is never checked against a public key and an RS256 one never against the shared secret."""
    if jwt.get_unverified_header(token).get("alg") == "RS256":
        from . import oidc

        return oidc.decode_realm_token(token)
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
