# Changelog — identity

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Plan user limit. `create_user` refuses the person who would take the organisation past its plan's `users`
  limit with `PlanLimitReachedError`, before anything is written; `POST /users` answers `409` with
  `{"code": "plan_limit_reached", "limit": "users", "allowed", "used"}`. The limit comes through the new
  `hooks.user_limit(db, organisation_id)` (None, the default, is no limit), which apps/backend wires to
  billing's `user_limit`, so identity imports nothing. New `count_active_users(db, organisation_id)`, the
  figure the limit and billing's usage count. On Postgres the count and the insert run under a
  per-organisation advisory lock (`lock_user_seats`, `pg_advisory_xact_lock`), so two requests at the limit
  minus one cannot both pass (review of PR 363).
- Sign in through the organisation's Keycloak realm (ADR-0006, #76). `eos_core.security.decode_token` also
  accepts RS256 tokens whose issuer is `<EOS_OIDC_ISSUER_BASE>/realms/<slug>`, verified against the realm's
  cached JWKS with audience `EOS_OIDC_CLIENT_ID`; this service maps them to a user by the new
  `identity_user.oidc_subject` column (migration `identity_0002`, unique per organisation), linking the
  subject on first sight by the token's verified email. New public routes: `GET /auth/oidc/config?slug=`
  (what the sign-in page needs for the PKCE code flow; 404 when the organisation has no realm) and
  `POST /auth/oidc/callback` (redeems the code, verifies the id token and answers like `/auth/login` with
  the platform's own token; 403 `no_account` for a person identity does not know). Password login stays;
  the super admin never uses OIDC. Realm setup for a pilot organisation: README and
  `tools/scripts/keycloak-realm.sh`. Event `identity.user.oidc_linked`.
  Review of #365: a realm must be in `EOS_OIDC_REALMS` before any key fetch (removing a slug stops its
  tokens at once); only access tokens (`typ: Bearer`) are bearer tokens and the callback accepts only an ID
  token (`typ: ID`), `azp` must be our client when present; the JWKS fetch runs outside the cache lock with
  `EOS_OIDC_JWKS_TIMEOUT` (2 s), at most one unknown-`kid` refetch per realm per 60 s, failures remembered
  for 30 s, at most four fetches at once.
- No person may hold the `service` role. `create_user` refuses it before writing anything, so every way a
  role is assigned (`POST /users`, tenancy's registration, the super-admin seed) is covered, and `POST /users`
  answers 403. `current_principal` also drops it from any token, so a row or token that already carries it
  grants nothing. `service` is the catalogue holder of keys meant for no person, such as
  `notification:message:send`.
- Module scaffolded.
