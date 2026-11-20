"""Who is really acting (security review N3, #672). A super admin's impersonation token (tenancy) names the
organisation user in `sub`, whose permissions apply, and the super admin in `imp`. Every event the request
publishes must name both: this middleware puts `imp` into eos_core's request context for the whole request,
before any dependency or route runs, and `eos_core.events.publish()` copies it onto the envelope's
`impersonated_by`. Nothing else changes: the route still sees the impersonated user as the principal.

Pure ASGI rather than BaseHTTPMiddleware: the route runs in this middleware's own task, so the context it sets is
the one the route (and the thread pool a sync route runs in, which copies it) sees."""

from __future__ import annotations

import jwt
from eos_api_gateway import token_claims
from eos_core.events import impersonation
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send


class ImpersonationContext:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            # decoded once per request: the limiter has usually done it already (eos_api_gateway.token_claims)
            claims = await token_claims(HTTPConnection(scope)) or {}
        except jwt.PyJWTError:
            claims = {}  # the route refuses the token itself; there is nobody to attribute
        with impersonation(claims.get("imp")):
            await self.app(scope, receive, send)
