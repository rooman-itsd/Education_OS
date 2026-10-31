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
_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def configure_logging(fmt: str | None = None, level: str | None = None, stream: TextIO | None = None) -> None:
    """Route structlog and the standard library (uvicorn, SQLAlchemy, eos.*) through one formatter. Safe to call
    again: the root handler is replaced, not added to."""
    fmt = (fmt or os.environ.get("EOS_LOG_FORMAT", "json")).strip().lower()
    level = (level or os.environ.get("EOS_LOG_LEVEL", "INFO")).strip().upper()
    # A mistyped level must not stop the API from starting: fall back to INFO and say so once configured.
    bad_level = None if level in _LEVELS else level
    level = level if bad_level is None else "INFO"
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
    if bad_level is not None:
        logging.getLogger("eos.logging").warning("EOS_LOG_LEVEL=%s is not a log level; using INFO", bad_level)


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
        except Exception:
            # Here, with both ids bound; the server's own traceback line, written outside this middleware, has none.
            log.exception("unhandled error", method=request.method, path=request.url.path)
            raise
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


def _redact(text: Any) -> Any:
    return _EMAIL_RE.sub("[email]", text) if isinstance(text, str) else text


def scrub(event: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry's before_send: nothing personal leaves the server, and the ids that find the log lines are added.
    Local variables are off in init_sentry; any a frame still carries are dropped here too, and email addresses
    in exception messages, log messages and breadcrumbs are replaced by [email]."""
    for exc in (event.get("exception") or {}).get("values") or []:
        exc["value"] = _redact(exc.get("value"))
        for frame in (exc.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    for thread in (event.get("threads") or {}).get("values") or []:
        for frame in (thread.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    logentry = event.get("logentry") or {}
    for key in ("message", "formatted"):
        if key in logentry:
            logentry[key] = _redact(logentry[key])
    if "params" in logentry:
        logentry["params"] = [_redact(p) for p in logentry["params"]]
    if "message" in event:
        event["message"] = _redact(event["message"])
    for crumb in (event.get("breadcrumbs") or {}).get("values") or []:
        crumb["message"] = _redact(crumb.get("message"))
        crumb.pop("data", None)
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


def init_sentry(transport: Any = None) -> bool:
    """Start Sentry when EOS_SENTRY_DSN is set; otherwise nothing is sent anywhere. `transport` is for tests.

    No local variables (a password or an email in a function's locals would travel with every traceback), no
    request body and no source lines. The environment defaults to staging, so a host that forgets to set it is
    never reported as production."""
    dsn = os.environ.get("EOS_SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("EOS_ENVIRONMENT", "staging"),
        send_default_pii=False,
        include_local_variables=False,
        include_source_context=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=scrub,
        transport=transport,
    )
    return True
