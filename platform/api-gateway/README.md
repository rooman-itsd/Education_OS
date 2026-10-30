# api-gateway

**Domain:** platform
**Kind:** platform
**Status:** in-progress

The edge of the API host: security headers on every response and rate limits per client IP and per
organisation. Two middlewares (`eos_api_gateway.SecurityHeaders`, `eos_api_gateway.RateLimit`) that
`apps/backend` adds around every route; no routes, no tables, no permission keys.

## Scope
- Security headers on every response, the entitlement gate's and the limiter's refusals included:
  `Strict-Transport-Security` (only when the request came in over HTTPS, directly or as
  `X-Forwarded-Proto: https` from the proxy), `Content-Security-Policy: default-src 'none'; frame-ancestors
  'none'` (an API serves no page; the interactive docs at `/docs` and `/redoc` are the one exception),
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a minimal
  `Permissions-Policy`, and `Cache-Control: no-store` on `/api/` responses unless the route set its own.
- Rate limits as token buckets (`per_minute` sustained, `burst` at once): per client IP on every request,
  per organisation on top of it when the request carries a valid bearer token with an `org` claim (an
  invalid, expired or platform token draws from the IP bucket only), and a stricter bucket per address for
  `POST /identity/auth/login` and `POST /tenancy/register` (password guessing, bulk sign-ups). Over the
  limit: `429`, `Retry-After: <seconds>`, body `{"detail", "code": "rate_limited", "scope": "ip" |
  "organisation" | "auth", "retry_after"}`. `GET /api/v1/health` is never limited.
- Buckets live in the API process by default; with `EOS_REDIS_URL` set they live in Redis and every API
  process or replica counts against the same limits. While Redis is unreachable the API fails open (allows
  and logs) rather than refusing everything.

Not in scope: plan limits (users, students, storage). Those are enforced where the thing is created:
`platform/billing` exposes `plan_limits` / `user_limit` / `usage_vs_limits` (`GET /api/v1/billing/usage`),
and `platform/identity`'s `create_user` answers `409 plan_limit_reached` past the plan's user limit, through
a hook the host wires. Authentication and authorisation stay with identity and each module.

## Configuration
Every key, with its default, is in [config/env.example](config/env.example). The ones that matter in a
deployment:

| Key | Meaning |
|---|---|
| `EOS_RATE_LIMIT_IP_PER_MINUTE` / `_BURST` | per client address, every request. A campus behind one NAT address shares one bucket: size it for the whole campus, not one person |
| `EOS_RATE_LIMIT_ORG_PER_MINUTE` / `_BURST` | per organisation, all of its users together |
| `EOS_RATE_LIMIT_AUTH_PER_MINUTE` / `_BURST` | sign-in and sign-up, per client address |
| `EOS_TRUSTED_PROXIES` | which peers' `X-Forwarded-For` is believed (below) |
| `EOS_REDIS_URL` | share the buckets between API processes |
| `EOS_RATE_LIMIT_ENABLED`, `EOS_SECURITY_HEADERS` | `false` only for local dev and test suites that hammer one address |

Settings are read once, when `apps/backend` builds the app (`create_app()`), so a restart applies a change.

### The reverse proxy must pass the client address
The API sees the proxy as its peer. It believes `X-Forwarded-For` only when that peer is in
`EOS_TRUSTED_PROXIES` (default: loopback and the private ranges, where `infra/docker/nginx.public-vhost.conf`
runs), and takes as the client the rightmost address that is not itself a trusted proxy, so whatever a client
writes into the header is ignored. The proxy must therefore set

```
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

(`nginx.public-vhost.conf` does). Without the header every request would be one bucket, the proxy's; without
`X-Forwarded-Proto` no response carries `Strict-Transport-Security`. If the proxy is on a public address, set
`EOS_TRUSTED_PROXIES` to it. Never set `*` on an API port reachable by clients directly: any client could then
pick its own bucket.

## In the host
`apps/backend/config/modules.enabled.yaml` lists `api-gateway` under `platform`, which is what
`tools/scripts/py-setup.sh`, CI and the API image install (`tools/scripts/enabled-modules.py`); a platform
entry without `api/router.py` mounts nothing. `apps/backend/src/eos_backend/main.py` adds the middlewares,
innermost first: `EntitlementGate`, `RateLimit` (a refused request costs no database query), CORS (a browser
must be allowed to read a 429), `SecurityHeaders` outermost.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml) (the headers and the 429 every other contract inherits)
- Events: [contracts/events.yaml](contracts/events.yaml) (none)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml) (none: no routes)

## Layout
| Path | Purpose |
|---|---|
| `backend/src/eos_api_gateway/domain/bucket.py` | token bucket arithmetic, pure |
| `backend/src/eos_api_gateway/application/limiter.py` | which buckets a request draws from; client address behind the proxy; the `BucketStore` interface |
| `backend/src/eos_api_gateway/infrastructure/` | `MemoryStore` (in-process), `RedisStore` (Lua, atomic), `store_for(settings)` |
| `backend/src/eos_api_gateway/api/middleware.py` | `SecurityHeaders`, `RateLimit` |
| `backend/src/eos_api_gateway/settings.py` | `GatewaySettings.from_env()` |
| `backend/tests/` | both middlewares on a small app with a fake clock and the in-process store |

## Follow-ups
- Students and storage limits: no module counts students or stored bytes yet; `GET /billing/usage` reports
  them as `null`. Enforce them where student records and documents are created, once those modules exist.
- The `billing.usage-vs-limits` widget still counts users itself from `GET /identity/users`; it can read
  `GET /billing/usage` instead.
- Request logging and monitoring (the rest of this service's description) are not started.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
