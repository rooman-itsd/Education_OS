"""The two middlewares apps/backend adds. No router: the gateway adds headers and refusals, never routes."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from ..application.limiter import BucketStore, RateLimiter
from ..infrastructure import store_for
from ..settings import GatewaySettings
from .claims import token_claims

# An API serves JSON, never a page: nothing may load from it and nobody may frame it.
CSP = "default-src 'none'; frame-ancestors 'none'"
# FastAPI's interactive docs are pages that load Swagger UI from a CDN; they keep every other header.
CSP_EXEMPT = ("/docs", "/docs/oauth2-redirect", "/redoc")
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
API_PREFIX = "/api/"
_BODYLESS = ("GET", "HEAD", "OPTIONS", "DELETE")
# Sign-in answers with one of these when the credentials were wrong; any other answer (200, 422, 5xx) is not a
# failed guess and does not use up an attempt.
_FAILED_LOGIN = (401, 403)
# A sign-in or sign-up body is an email, a password, a name and a slug: far below this. The gateway reads at most
# this much of a body on the auth paths (to find a sign-in's email for the per-account bucket) and answers 413
# past it, so padding a body cannot slip past the per-account bucket.
_AUTH_BODY_LIMIT = 16 * 1024


class BodyTooLargeError(Exception):
    """An auth path's body is larger than `_AUTH_BODY_LIMIT`."""


def _is_https(request: Request) -> bool:
    """The proxy terminates TLS (infra/docker/nginx.public-vhost.conf sets X-Forwarded-Proto). The header is
    taken at face value: HSTS is ignored by browsers over plain HTTP, so a forged one changes nothing."""
    if request.url.scheme == "https":
        return True
    proto = request.headers.get("x-forwarded-proto", "")
    return proto.split(",", 1)[0].strip().lower() == "https"


async def _read_bounded_body(request: Request) -> bytes | None:
    """The body of a request on an auth path, read chunk by chunk and at most `_AUTH_BODY_LIMIT` bytes, so a body
    without a Content-Length (chunked) cannot make the gateway buffer a large upload. Raises BodyTooLargeError past
    the limit (by Content-Length or by what arrived); None when the client went away mid-body. Every message
    read here is replayed to the route, which sees the whole body."""
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0  # unreadable: count what arrives instead
    if declared > _AUTH_BODY_LIMIT:
        raise BodyTooLargeError
    original = request.receive
    seen: list[Message] = []
    body = bytearray()
    complete = False
    while True:
        message = await original()
        seen.append(message)
        if message["type"] != "http.request":
            break  # the client went away
        body += message.get("body", b"")
        if len(body) > _AUTH_BODY_LIMIT:
            raise BodyTooLargeError  # stop reading: the request is refused, the rest is never read
        if not message.get("more_body", False):
            complete = True
            break

    async def replay() -> Message:
        return seen.pop(0) if seen else await original()

    request._receive = replay  # noqa: SLF001 (Starlette has no public way to put back what was read)
    return bytes(body) if complete else None


def _email_of(body: bytes | None) -> str | None:
    """The `email` of a sign-in body, for the per-account bucket; None when the body is not JSON or names no
    email (the route answers it, and the per-address bucket still applies)."""
    if body is None:
        return None
    try:
        parsed = json.loads(body or b"null")
    except (ValueError, UnicodeDecodeError):
        return None
    email = parsed.get("email") if isinstance(parsed, dict) else None
    return email if isinstance(email, str) and email.strip() else None


class SecurityHeaders(BaseHTTPMiddleware):
    """Outermost: every response, including the gate's and the limiter's refusals, carries the headers. A route
    that set one of them keeps its own value (setdefault): a page the API serves on purpose, such as the
    payment adapter's hand-off to the bank, sends its own Content-Security-Policy and keeps it."""

    def __init__(self, app, *, settings: GatewaySettings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or GatewaySettings.from_env()

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not self.settings.security_headers:
            return response
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        path = request.url.path
        if path not in CSP_EXEMPT:
            h.setdefault("Content-Security-Policy", CSP)
        if path.startswith(API_PREFIX):
            h.setdefault("Cache-Control", "no-store")
        if _is_https(request):
            h.setdefault("Strict-Transport-Security", f"max-age={self.settings.hsts_max_age}; includeSubDomains")
        return response


class RateLimit(BaseHTTPMiddleware):
    """429 with Retry-After and {"code": "rate_limited"} when a client address, a user, an organisation, sign-in
    from an address or sign-in to one account from an address is over its bucket; 413 {"code": "body_too_large"}
    for a sign-in or sign-up body past 16 KiB. Sits inside CORS (a browser must be allowed to read the 429) and
    outside the entitlement gate (a refused request costs no database query). The bearer token is decoded here,
    once (`claims.token_claims`), and the gate reuses it."""

    def __init__(
        self,
        app,
        *,
        settings: GatewaySettings | None = None,
        store: BucketStore | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(app)
        settings = settings or GatewaySettings.from_env()
        self.limiter = RateLimiter(settings, store if store is not None else store_for(settings), clock)

    async def dispatch(self, request: Request, call_next):
        if not self.limiter.enabled:
            return await call_next(request)
        path = request.url.path
        peer = request.client.host if request.client else None
        forwarded_for = request.headers.get("x-forwarded-for")
        email = None
        if request.method not in _BODYLESS and self.limiter.is_bounded_body_path(path):
            try:
                body = await _read_bounded_body(request)
            except BodyTooLargeError:
                return _refusal(413, f"the request body is larger than {_AUTH_BODY_LIMIT} bytes", "body_too_large", {})
            if self.limiter.is_login_path(path):
                email = _email_of(body)
        try:
            claims = await token_claims(request)
        except jwt.PyJWTError:
            claims = None  # an invalid token is anonymous here; the routes and the gate refuse it
        denied = await self.limiter.check(
            path=path, peer=peer, forwarded_for=forwarded_for, claims=claims, login_email=email
        )
        if denied is None:
            response = await call_next(request)
            if email and response.status_code not in _FAILED_LOGIN:
                # check() charged the account's bucket up front; only a refused sign-in is an attempt
                await self.limiter.refund_login(peer=peer, forwarded_for=forwarded_for, email=email)
            return response
        noun = {
            "ip": "this address",
            "user": "your account",
            "organisation": "your organisation",
            "auth": "sign-in from this address",
            "login": "sign-in to this account from this address",
        }
        return _refusal(
            429,
            f"too many requests for {noun[denied.scope]}; retry after {denied.retry_after} seconds",
            "rate_limited",
            {"scope": denied.scope, "retry_after": denied.retry_after},
            headers={"Retry-After": str(denied.retry_after)},
        )


def _refusal(status: int, detail: str, code: str, extra: dict, headers: dict[str, str] | None = None):
    return JSONResponse({"detail": detail, "code": code, **extra}, status_code=status, headers=headers)
