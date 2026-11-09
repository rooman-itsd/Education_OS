"""The request's bearer token, decoded once per request. The limiter needs its `org` and `sub`, the host's
entitlement gate its `org` again, and the limiter's log line names the user: each asks `token_claims(request)`,
and only the first call decodes. The answer (claims, or the reason the token was refused) is kept on
`request.state` (`token_claims`, `token_error`), which every middleware and route of the request shares.

A realm token (RS256, ADR-0006) is decoded in the thread pool: verifying it may fetch the realm's JWKS and
asks identity's resolver, which queries the database, and neither may hold the event loop. The platform's own
HS256 tokens are one HMAC and are decoded in place."""

from __future__ import annotations

import jwt
from eos_core.security import decode_token
from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection

CLAIMS = "token_claims"  # request.state attribute: the claims dict, or None without a bearer token
ERROR = "token_error"  # request.state attribute: the jwt.PyJWTError a bearer token was refused with
_UNSET = object()


def bearer(authorization: str | None) -> str | None:
    """The token of an `Authorization: Bearer <token>` header (an empty one is refused as invalid), or None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


async def decode(token: str) -> dict:
    """`eos_core.security.decode_token`, off the event loop when it may block (a realm token)."""
    if jwt.get_unverified_header(token).get("alg") == "RS256":
        return await run_in_threadpool(decode_token, token)
    return decode_token(token)


async def token_claims(request: HTTPConnection) -> dict | None:
    """The claims of the request's bearer token; None when it has none. Raises the `jwt.PyJWTError` an invalid
    token was refused with, the same one on every call. Decodes at most once per request."""
    state = request.state
    cached = getattr(state, CLAIMS, _UNSET)
    if cached is not _UNSET:
        error = getattr(state, ERROR, None)
        if error is not None:
            raise error
        return cached
    token = bearer(request.headers.get("authorization"))
    claims: dict | None = None
    try:
        claims = await decode(token) if token is not None else None
    except jwt.PyJWTError as e:
        setattr(state, CLAIMS, None)
        setattr(state, ERROR, e)
        raise
    setattr(state, CLAIMS, claims)
    setattr(state, ERROR, None)
    return claims
