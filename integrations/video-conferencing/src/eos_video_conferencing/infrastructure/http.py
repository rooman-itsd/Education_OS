"""The only place that talks HTTP to a provider. The httpx client is injectable (`client_factory`), so tests give it a
MockTransport and no test ever opens a socket. Headers, bodies and tokens are never logged here."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx

from ..domain.errors import AdapterError

ClientFactory = Callable[[], httpx.Client]
MAX_RETRY_AFTER_S = 24 * 3600


def seconds_until_midnight_utc(now: datetime) -> int:
    nxt = (now.astimezone(UTC) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((nxt - now).total_seconds()))


def retry_after(response: httpx.Response) -> int | None:
    """Retry-After in seconds (the HTTP-date form is rare for these APIs and is treated as absent), bounded."""
    raw = response.headers.get("retry-after", "").strip()
    if raw.isdigit():
        return min(int(raw), MAX_RETRY_AFTER_S)
    return None


def provider_code(response: httpx.Response) -> str:
    """The provider's machine code when the body has a short one, else the HTTP status. Never prose."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("code", "errorCode"):
            value = body.get(key)
            if (
                isinstance(value, (int, str))
                and not isinstance(value, bool)
                and re.fullmatch(r"[\w.\-]{1,40}", str(value))
            ):
                return str(value)
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("code"), str) and re.fullmatch(r"[\w.\-]{1,60}", err["code"]):
            return err["code"]
    return str(response.status_code)


def map_status(response: httpx.Response) -> AdapterError:
    """The generic mapping of docs/prd.md, "Error mapping". Providers refine it before falling back to this."""
    status = response.status_code
    pc = provider_code(response)
    if status == 429:
        return AdapterError(
            "throttled", "the provider rate-limited the call", provider_code=pc, retry_after_s=retry_after(response)
        )
    if status in (401, 403):
        return AdapterError("auth_failed", "the provider refused the credentials or the token", provider_code=pc)
    if status == 404:
        return AdapterError("not_found", "the provider has no such object", provider_code=pc)
    if status == 409:
        return AdapterError("conflict", "the provider's state does not allow this", provider_code=pc)
    if status in (400, 422):
        return AdapterError("invalid_request", "the provider rejected the request", provider_code=pc)
    if status >= 500:
        return AdapterError("provider_error", "the provider failed", provider_code=pc)
    return AdapterError("rejected", "the provider refused the request", provider_code=pc)


class Http:
    def __init__(self, client_factory: ClientFactory | None = None, timeout_s: int = 15) -> None:
        self._factory = client_factory or (lambda: httpx.Client(timeout=timeout_s, follow_redirects=False))

    def send(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            with self._factory() as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError as e:  # timeouts, connection and TLS failures: nothing of the exception is kept
            raise AdapterError("transport_unavailable", f"could not reach the provider ({type(e).__name__})") from e

    @contextmanager
    def stream(self, method: str, url: str, **kwargs) -> Iterator[httpx.Response]:
        try:
            with self._factory() as client, client.stream(method, url, **kwargs) as response:
                yield response
        except httpx.HTTPError as e:
            raise AdapterError("transport_unavailable", f"could not reach the provider ({type(e).__name__})") from e


def json_body(response: httpx.Response) -> dict:
    """The JSON object of an answer; anything else is the provider failing, not our bug."""
    if response.status_code == 204 or not response.content:
        return {}
    try:
        body = response.json()
    except ValueError as e:
        raise AdapterError("provider_error", "the provider answered with something that is not JSON") from e
    if not isinstance(body, dict):
        raise AdapterError("provider_error", "the provider answered with an unexpected shape")
    return body
