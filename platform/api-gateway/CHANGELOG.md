# Changelog — api-gateway

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
