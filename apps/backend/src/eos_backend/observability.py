"""Logs and errors for the API host (#91).

Every log line is one JSON object (EOS_LOG_FORMAT=json, the default; `console` for reading locally) and carries
the request's `request_id` and `organisation_id`, the API's own messages and uvicorn's and SQLAlchemy's alike. One
`request` line is written per request: method, route template, status, duration. The organisation comes only from a
token the API verified, never from a claim it did not check, so a forged token cannot put another organisation's id
in the logs. The request id is the caller's X-Request-ID when it is a plain token, else a new one, and is returned
in the response's X-Request-ID so a user's report can be matched to its lines.

Sentry receives unhandled errors only when EOS_SENTRY_DSN is set, tagged with the organisation and request ids and
with nothing personal: no request body, cookies, headers, query string, user email or IP (DPDP)."""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import uuid
from typing import Any, TextIO

import jwt
import structlog
from eos_core.security import decode_token
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = structlog.get_logger("eos.request")

REQUEST_ID = "X-Request-ID"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def configure_logging(fmt: str | None = None, level: str | None = None, stream: TextIO | None = None) -> None:
    """Route structlog and the standard library (uvicorn, SQLAlchemy, eos.*) through one formatter. Safe to call
    again: the root handler is replaced, not added to."""
    fmt = (fmt or os.environ.get("EOS_LOG_FORMAT", "json")).strip().lower()
    level = (level or os.environ.get("EOS_LOG_LEVEL", "INFO")).strip().upper()
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer = structlog.dev.ConsoleRenderer() if fmt == "console" else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # The `request` line below replaces uvicorn's access log; its error log goes through the handler above.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    # httpx logs every outgoing URL at INFO, query string included (a token or an address can ride on one).
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _verified_organisation(request: Request) -> str | None:
    """The `org` of the API's own (HS256) token, verified, without a database query. A Keycloak (RS256) token is
    verified by the entitlement gate on feature modules, which records its organisation for this log line; other
    tokens and forged ones give None."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        if jwt.get_unverified_header(token).get("alg") != "HS256":
            return None
        return decode_token(token).get("org")
    except jwt.PyJWTError:
        return None


class RequestContext(BaseHTTPMiddleware):
    """Outermost middleware: a request id and the verified organisation for every log line of the request, and
    one `request` line when it ends."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID, "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        organisation_id = _verified_organisation(request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, organisation_id=organisation_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID] = request_id
            return response
        finally:
            organisation_id = getattr(request.state, "organisation_id", None) or organisation_id
            route = request.scope.get("route")
            path = request.url.path
            # The route template is the module's own (/auth/me); the module comes from /api/v1/<module>/.
            module = path.split("/")[3] if path.startswith("/api/v1/") and path.count("/") >= 3 else None
            log.info(
                "request",
                method=request.method,
                module=module,
                route=getattr(route, "path", None),
                path=path,  # no query string: it can carry personal data
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                organisation_id=organisation_id,
            )
            structlog.contextvars.clear_contextvars()


_SAFE_HEADERS = {"user-agent", "content-type", "content-length", "accept"}


def scrub(event: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry's before_send: nothing personal leaves the server, and the ids that find the log lines are added."""
    request = event.get("request") or {}
    for key in ("data", "cookies", "query_string", "env"):
        request.pop(key, None)
    headers = request.get("headers") or {}
    request["headers"] = {k: v for k, v in headers.items() if k.lower() in _SAFE_HEADERS}
    if request:
        event["request"] = request
    event.pop("user", None)
    context = structlog.contextvars.get_contextvars()
    tags = event.setdefault("tags", {})
    for key in ("organisation_id", "request_id"):
        if context.get(key):
            tags[key] = context[key]
    return event


def init_sentry() -> bool:
    """Start Sentry when EOS_SENTRY_DSN is set; otherwise nothing is sent anywhere."""
    dsn = os.environ.get("EOS_SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("EOS_ENVIRONMENT", "staging"),
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=scrub,
    )
    return True
