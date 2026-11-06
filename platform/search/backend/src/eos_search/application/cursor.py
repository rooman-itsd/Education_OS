"""Signed, expiring cursors (docs/prd.md, decision 7).

A cursor is `base64url(json).base64url(hmac-sha256)`. It carries the user id and a hash of what was asked (q, types,
filters), so a cursor from another user or another query is refused, and an expiry, so an old one is too. There is no
offset: a cursor holds the sort values of the last hit, for `search_after`."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping, Sequence

from ..domain.errors import SearchError

MAX_CURSOR_LENGTH = 2000
BAD_CURSOR = "the cursor is not valid for this request"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def query_hash(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:32]


def sign(secret: str, payload: Mapping, *, ttl_seconds: int, now: float | None = None) -> str:
    body = {**payload, "exp": int((time.time() if now is None else now) + ttl_seconds)}
    data = _b64(json.dumps(body, separators=(",", ":")).encode())
    mac = _b64(hmac.new(secret.encode(), data.encode(), hashlib.sha256).digest())
    return f"{data}.{mac}"


def verify(secret: str, token: str, *, user_id: str, bound_to: str, now: float | None = None) -> dict:
    """The payload of a genuine, unexpired cursor issued to this user for this request. Anything else is a 422
    with the same sentence, so the answer does not tell which check failed."""
    if not isinstance(token, str) or not token or len(token) > MAX_CURSOR_LENGTH or token.count(".") != 1:
        raise SearchError(422, BAD_CURSOR)
    data, mac = token.split(".")
    expected = _b64(hmac.new(secret.encode(), data.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(mac.encode(), expected.encode()):
        raise SearchError(422, BAD_CURSOR)
    try:
        payload = json.loads(_unb64(data))
    except (ValueError, UnicodeDecodeError):
        raise SearchError(422, BAD_CURSOR) from None
    if not isinstance(payload, dict):
        raise SearchError(422, BAD_CURSOR)
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, int | float) or exp < (time.time() if now is None else now):
        raise SearchError(422, BAD_CURSOR)
    if payload.get("u") != user_id or payload.get("h") != bound_to:
        raise SearchError(422, BAD_CURSOR)
    return payload


def sort_values(payload: Mapping) -> Sequence:
    """The `search_after` values in a verified cursor, checked once more for shape."""
    s, n = payload.get("s"), payload.get("n")
    if (
        not isinstance(s, list)
        or len(s) != 2
        or isinstance(s[0], bool)
        or not isinstance(s[0], int | float)
        or s[0] != s[0]
        or not isinstance(s[1], str)
        or isinstance(n, bool)
        or not isinstance(n, int)
        or n < 0
    ):
        raise SearchError(422, BAD_CURSOR)
    return s
