# api-gateway

**Domain:** platform
**Kind:** platform
**Status:** in-progress

The edge of the API host: security headers on every response and rate limits per client IP, per user and
per organisation. Two middlewares (`eos_api_gateway.SecurityHeaders`, `eos_api_gateway.RateLimit`) that
`apps/backend` adds around every route; no routes, no tables, no permission keys.

## Scope
- Security headers on every response, the entitlement gate's and the limiter's refusals included:
  `Strict-Transport-Security` (only when the request came in over HTTPS, directly or as
  `X-Forwarded-Proto: https` from the proxy), `Content-Security-Policy: default-src 'none'; frame-ancestors
  'none'` (an API serves no page; the interactive docs at `/docs` and `/redoc` are the one exception),
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a minimal
  `Permissions-Policy`, and `Cache-Control: no-store` on `/api/` responses unless the route set its own.
- Rate limits as token buckets (`per_minute` sustained, `burst` at once). A request with a valid bearer
  token that carries an `org` claim draws from its user's bucket (the `sub` claim), then its organisation's,
  the ceiling for all its users together; any other request (no token, an invalid, expired or platform
  token) draws from its client address's bucket (an IPv6 client by its /64). Sign-in and sign-up
  (`POST /identity/auth/login`, the OIDC `/identity/auth/oidc/callback` and `/config`,
  `POST /tenancy/register`) and every module's anonymous public routes (`/api/v1/<module>/public/...`, e.g.
  the admissions application form) also draw from a stricter bucket per address, and sign-in from one more
  per account and address (the `email` of the body; only a refused sign-in uses up an attempt). A request
  that one bucket refuses is given back to the buckets it was already charged to. Over the limit: `429`,
  `Retry-After: <seconds>`, body `{"detail", "code": "rate_limited", "scope": "ip" | "user" |
  "organisation" | "auth" | "login", "retry_after"}`. A sign-in, OIDC or sign-up body over 16 KiB: `413`
  `{"code": "body_too_large"}`. `GET /api/v1/health` is never limited.
- The bearer token is decoded once per request (`eos_api_gateway.token_claims`): the limiter decodes it and
  keeps the claims on `request.state.token_claims` (or the refusal on `request.state.token_error`), and the
  host's entitlement gate reuses them. A Keycloak realm token (RS256) is decoded in the thread pool, since
  verifying it may fetch the realm's keys and asks identity, which queries the database.
- Buckets live in the API process by default (at most 50 000, the least recently used dropped first, so a
  flood of fresh addresses cannot grow the process); with `EOS_REDIS_URL` set they live in Redis, through
  the awaited `redis.asyncio` client, and every API process or replica counts against the same limits. While Redis is unreachable the API fails open (allows
  and logs) rather than refusing everything, and fails fast: 0.1 s to connect, 0.25 s to answer, no client
  retries, and after a failure Redis is not asked again for 30 s.

Not in scope: plan limits (users, students, storage). Those are enforced where the thing is created:
`platform/billing` exposes `plan_limits` / `user_limit` / `usage_vs_limits` (`GET /api/v1/billing/usage`),
and `platform/identity`'s `create_user` answers `409 plan_limit_reached` past the plan's user limit, through
a hook the host wires. Authentication and authorisation stay with identity and each module.

## Configuration
Every key, with its default, is in [config/env.example](config/env.example). The ones that matter in a
deployment:

| Key | Default | Meaning |
|---|---|---|
| `EOS_RATE_LIMIT_IP_PER_MINUTE` / `_BURST` | 1200 / 1200 | per client address, requests without an organisation token |
| `EOS_RATE_LIMIT_USER_PER_MINUTE` / `_BURST` | 300 / 300 | per signed-in user (token `sub`) |
| `EOS_RATE_LIMIT_ORG_PER_MINUTE` / `_BURST` | 12000 / 12000 | per organisation, all of its signed-in users together (the ceiling) |
| `EOS_RATE_LIMIT_AUTH_PER_MINUTE` / `_BURST` | 60 / 60 | sign-in, sign-up and public routes, per client address |
| `EOS_RATE_LIMIT_LOGIN_PER_MINUTE` / `_BURST` | 10 / 10 | sign-in, per account and client address (email digest + address); only 401/403 answers count |
| `EOS_TRUSTED_PROXIES` | loopback | which peers' `X-Forwarded-For` is believed (below); **set it in production** |
| `EOS_REDIS_URL` | empty | share the buckets between API processes |
| `EOS_RATE_LIMIT_ENABLED`, `EOS_SECURITY_HEADERS` | `true` | the emergency switch (below); `false` for test suites that hammer one address. true/false, 1/0, yes/no or on/off; anything else stops start-up |
| `EOS_HSTS_MAX_AGE` | 31536000 | `Strict-Transport-Security` max-age, seconds |

Settings are read once, when `apps/backend` builds the app (`create_app()`), so a restart applies a change.
`infra/docker/docker-compose.api.yml` passes every key from `infra/docker/.env.api`, with these defaults.

### Sizing the limits
A school is not one person per address. A campus usually reaches the API through one NAT address, and a
class signs in at the same moment when a lesson starts. The defaults follow from that:

- **Signed-in traffic is not charged to the address.** Once a user has a token, their own bucket and their
  organisation's are the bound; the address's bucket is left to anonymous traffic. Otherwise one busy
  campus would exhaust its own address and every later request, signed in or not, would get 429.
- **Per user (300 a minute, burst 300)** keeps one client from emptying the organisation's bucket for
  everyone: a student's script or a stuck page meets its own limit, while the teachers and admins of the
  same organisation carry on. A person clicking through dashboards (a page load fires a handful of widget
  requests) stays far below 5 requests a second sustained, and a full burst covers dozens of page loads at
  once.
- **Per organisation (12000 a minute, burst 12000)** is the ceiling for all its users together. It is sized
  for a results day: 500 users of one organisation each loading a 24-widget dashboard within the same
  minute is 12 000 requests, served from the burst while the bucket refills at 200 a second. A larger
  organisation raises `EOS_RATE_LIMIT_ORG_*`; a refusal names `scope=organisation` in the log.
- **The address bucket (1200 a minute)** meters only anonymous requests: the sign-in page's calls, public
  pages, and clients that have not signed in yet. A whole campus shares it, so it is sized for a campus,
  not for one person; a single abusive client is still held to 20 requests a second.
- **Sign-in per address (60 a minute, burst 60)** lets a lab of 40 sign in together, with room for typos,
  while bulk sign-ups and broad password spraying from one address stay slow.
- **Sign-in per account and address (10 a minute)** is what stops guessing one person's password from one
  place: the bucket is keyed on the email and the client address together, and only an answer of 401 or 403
  uses up an attempt (a successful sign-in, or a malformed request, is given back). So ten wrong passwords
  for one email from one address meet a 429 for that pair, while the account's owner, signing in from
  elsewhere, is untouched; an attacker naming a known admin's email cannot keep the admin out. Guessing
  from many addresses is bounded by the per-address buckets above and, in production, by the proxy. A lab
  signing in is 40 accounts, one attempt each, so it never meets this bucket. The key is a digest of the
  email, so neither Redis nor the logs hold it. At most 16 KiB of a sign-in body are read to find the email
  (chunked bodies included); a larger one is refused with `413`, so padding the body cannot skip this
  bucket, and an unreadable one (not JSON, no email) is held to the address buckets only.
- **IPv6 by /64.** An IPv6 client usually holds a whole /64 and can take a fresh address in it for every
  request, so the address, sign-in and per-account buckets key IPv6 by its /64 (an IPv4-mapped address by
  its IPv4 address).
- **A refused request costs nothing elsewhere.** When one bucket refuses, the tokens the request already took
  from the others (a sign-in's auth and per-account buckets when the address bucket refuses, a user's own
  bucket when the organisation's refuses) are given back.

Behind a reverse proxy set `EOS_TRUSTED_PROXIES`: while it is unset every anonymous request, sign-ins
included, keys on the proxy's address and shares one bucket, and the API logs a warning at start-up
(outside `EOS_DEV_MODE`).

Raise `EOS_RATE_LIMIT_AUTH_*` for a campus that signs in more than 60 people within a minute, and
`EOS_RATE_LIMIT_ORG_*` for an organisation larger than the results-day sizing above (refusals are logged
as `rate limited scope=...`).

### Emergency switch
If the limits refuse legitimate traffic in production, switch them off without a code change: on the API
host set `EOS_RATE_LIMIT_ENABLED=false` in `infra/docker/.env.api`, then run
`docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d` (Compose
recreates the API container with the new value; no rebuild). Set it back to `true` the same way once the
limits are raised. `EOS_SECURITY_HEADERS=false` is the same kind of switch for the headers.

### The reverse proxy must pass the client address
The API sees the proxy as its peer. It believes `X-Forwarded-For` only when that peer is in
`EOS_TRUSTED_PROXIES`, and reads the chain from the right: the client is the first hop that is not itself a
trusted proxy, so whatever a client writes into the header is ignored. The default is **loopback only**:
trusting whole private ranges would let anyone on the office LAN or VPN forge the header and get a fresh
bucket per request. **In production set `EOS_TRUSTED_PROXIES` to the reverse proxy's address** (the nginx
container, as the API host sees it); `tools/scripts/deploy-api-lxc.sh` writes it into `.env.api`, and
`infra/docker/.env.api.example` has the key. Without it every request is the proxy's one bucket.
The proxy must also set

```
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

(`nginx.public-vhost.conf` does). Without `X-Forwarded-Proto` no response carries
`Strict-Transport-Security`. `*` makes every direct peer a proxy and takes the rightmost hop as the client;
never set it on an API port that clients can reach directly.

## In the host
`apps/backend/config/modules.enabled.yaml` lists `api-gateway` under `platform`, which is what
`tools/scripts/py-setup.sh`, CI and the API image install (`tools/scripts/enabled-modules.py`).
`module.yaml` declares `router: false` (middleware only), so the host mounts nothing for it; any other entry
without `api/router.py` still stops start-up. `apps/backend/src/eos_backend/main.py` adds the middlewares,
innermost first: `EntitlementGate`, `RateLimit` (a refused request costs no database query), CORS (a browser
must be allowed to read a 429), `SecurityHeaders` outermost.

### Pages the API serves on purpose
`Content-Security-Policy: default-src 'none'` suits JSON and blanks any page. A route that returns a page
sets its own policy, and `SecurityHeaders` keeps it (it only fills headers the response does not have; the
same goes for `Referrer-Policy`). The SBI ePay hand-off (`integrations/payment-sbiepay`,
`GET /payments/{reference}/redirect`) does so: a nonce for its one inline script, `form-action 'self' https:`
(browsers apply `form-action` to the redirects after the POST too, and the gateway may redirect to a bank or
3-D Secure page on another origin) and `Referrer-Policy: strict-origin-when-cross-origin`, so the POST to the
gateway carries the merchant's origin.

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
