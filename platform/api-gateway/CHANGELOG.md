# Changelog — api-gateway

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Second review of PR 363 (contract 0.2.0):
  - a per-user bucket (`EOS_RATE_LIMIT_USER_*`, 300/min, keyed on the token's `sub` within its organisation)
    is checked before the organisation's, so one user cannot rate-limit the whole organisation; the
    organisation's default is raised to 12000/min, burst 12000 (500 users on a results day), and `scope`
    gains `user`;
  - a sign-in or sign-up body over 16 KiB answers `413 body_too_large` instead of skipping the per-account
    bucket;
  - `/api/v1/identity/auth/oidc/callback` and `/config` are auth paths;
  - the Redis store uses `redis.asyncio` (the Lua scripts and the fail-open policy are unchanged), and the
    bearer token is decoded once per request (`token_claims`, kept on `request.state.token_claims`; a realm
    token in the thread pool), which the host's entitlement gate reuses;
  - IPv6 clients are keyed by their /64; `MemoryStore` holds at most 50 000 buckets, dropping the least
    recently used;
  - `EOS_RATE_LIMIT_ENABLED` and `EOS_SECURITY_HEADERS` refuse anything but true/false, 1/0, yes/no or
    on/off at start-up, naming the key;
  - a request one bucket refuses is given back to the buckets already charged (on sign-in: the auth and
    per-account buckets when the address bucket refuses);
  - `SecurityHeaders` keeps a route's own `Referrer-Policy` like its `Content-Security-Policy` (tested).
- Review of PR 363 (Srujan): the per-account sign-in bucket is keyed on the email digest and the client
  address, so ten failed guesses from one address no longer lock the account out for its owner elsewhere,
  and it is charged only for a refused sign-in (401 or 403): the middleware gives the attempt back (new
  `BucketStore.refund`, in memory and in Redis) for any other answer. The per-address auth bucket stays the
  broad limit. `_login_email` reads at most 16 KiB of the body, chunked or not, and replays what it read to
  the route; past that it falls back to the address buckets. `apps/backend` logs one warning at start-up
  when `EOS_TRUSTED_PROXIES` is unset (still the loopback default) outside dev mode. `RateLimit` no longer
  discards a store passed in while it is empty.
- Review of PR 363: signed-in requests are charged to their organisation's bucket only, not to the client
  address; defaults raised for schools behind one NAT address (IP 1200/min, sign-in 60/min per address) and a
  per-account sign-in bucket (`EOS_RATE_LIMIT_LOGIN_*`, 10/min, keyed by a digest of the email) added;
  public `/api/v1/<module>/public/...` routes share the sign-in bucket. `EOS_TRUSTED_PROXIES` defaults to
  loopback only, and a chain where every hop is a trusted proxy resolves to the rightmost hop, never the
  client-written one. A Redis outage fails open fast (0.1 s connect, no retries, skipped for 30 s).
  `SecurityHeaders` keeps a `Content-Security-Policy` the route set. `module.yaml` declares `router: false`.
- `SecurityHeaders` middleware: `Strict-Transport-Security` (HTTPS requests only, directly or by
  `X-Forwarded-Proto`), `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a minimal
  `Permissions-Policy`, and `Cache-Control: no-store` on `/api/` responses. `EOS_SECURITY_HEADERS=false`
  switches them off for local tooling.
- `RateLimit` middleware: token buckets per client IP (X-Forwarded-For believed from `EOS_TRUSTED_PROXIES`
  only), per organisation (the `org` claim of a valid bearer token) and a stricter one per address for
  sign-in and sign-up; `429` with `Retry-After` and `{"code": "rate_limited", "scope": ..}`; `/api/v1/health`
  exempt. Buckets in-process, or in Redis when `EOS_REDIS_URL` is set (fail open while it is unreachable).
- Mounted by apps/backend outside the entitlement gate; enabled through `platform: [.., api-gateway]` in
  `apps/backend/config/modules.enabled.yaml` (a platform entry with no router mounts nothing).
- Module scaffolded.
