"""The OAuth 2.0 token calls every provider shares: a form POST to a token URL, an answer with access_token and maybe
refresh_token and expiry. Nothing here logs or returns a secret except in the dict the hub is meant to store."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta

from ...domain.errors import AdapterError
from ..http import Http, json_body, map_status, provider_code
from .base import integer, when


def basic(client_id: str, client_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def token_call(
    http: Http, url: str, form: dict, now: datetime, *, headers: dict | None = None, default_ttl: int = 3600
) -> dict:
    """POST the form; returns {secrets, expires_at, granted_scopes, raw} where raw is the provider's answer for the
    caller to read extra fields (athlete id, user id) from. A refused code or token is auth_failed; throttling and 5xx
    keep their own codes."""
    r = http.send("POST", url, data=form, headers=headers or {})
    if r.status_code >= 500 or r.status_code == 429:
        raise map_status(r)
    if r.status_code >= 400:
        raise AdapterError(
            "auth_failed", "the provider refused the code or the refresh token", provider_code=provider_code(r)
        )
    body = json_body(r)
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise AdapterError("provider_error", "the provider's token answer has no access token")
    secrets = {"access_token": access}
    if isinstance(body.get("refresh_token"), str) and body["refresh_token"]:
        secrets["refresh_token"] = body["refresh_token"]
    expires: datetime | None = None
    if isinstance(body.get("expires_at"), (int, float)) and not isinstance(body["expires_at"], bool):
        expires = when(body["expires_at"])
    elif body.get("expires_in") is not None:
        ttl = integer(body.get("expires_in"), 10**9) or default_ttl
        expires = now + timedelta(seconds=ttl)
    scope = body.get("scope")
    scopes = scope.replace(",", " ").split()[:100] if isinstance(scope, str) else []
    return {
        "secrets": secrets,
        "expires_at": expires.isoformat() if expires else None,
        "granted_scopes": scopes,
        "raw": body,
    }
