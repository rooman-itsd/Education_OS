"""The edge of the API host: security headers on every response and rate limits per client IP and per
organisation and user. Middleware only; this service mounts no routes. apps/backend adds `SecurityHeaders` and
`RateLimit` outside the entitlement gate (see README.md), and the gate reads the bearer token's claims through
`token_claims`, which decodes the token once per request."""

from .api.claims import token_claims
from .api.middleware import RateLimit, SecurityHeaders
from .settings import GatewaySettings

__all__ = ["GatewaySettings", "RateLimit", "SecurityHeaders", "token_claims"]
