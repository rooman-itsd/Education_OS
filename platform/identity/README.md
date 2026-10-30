# identity

**Domain:** platform
**Kind:** platform
**Status:** in progress

SSO (SAML / OAuth2 / OIDC), RBAC with fine-grained permissions, MFA, session management.

## Scope
Who a caller is and what they may do: users, roles and the permission catalogues; password sign-in and
sign-in through the organisation's Keycloak realm (ADR-0006); `current_principal` for every router. It is
the system of record for users and organisation membership. It is not the identity provider: passwords
policy, MFA, Google / Microsoft / SAML brokering live in Keycloak, and organisation status and slugs come
from platform/tenancy through hooks apps/backend fills at startup (this module imports no other module).

## Signing in through Keycloak (ADR-0006)

One Keycloak realm per organisation, named by the slug, served by the public proxy under
`https://<host>/auth/` (`infra/docker/docker-compose.api.yml`, profile `oidc`). Keycloak authenticates;
identity decides who has an account and which roles they hold. The super admin never uses OIDC. Password
login (`POST /auth/login`) stays for every user (ADR-0006 decision 5).

How a sign-in runs:

1. The sign-in page asks `GET /auth/oidc/config?slug=<slug>`. 404 means the organisation has no realm (or
   OIDC is off); 200 returns the realm's `authorization_endpoint`, `token_endpoint`, `client_id`
   (`education-os-web`), `scope` and `code_challenge_method: S256`.
2. The page starts the authorization code flow with PKCE against `authorization_endpoint` and gets a
   `code` back on its redirect URI.
3. It posts `{code, code_verifier, redirect_uri, slug}` to `POST /auth/oidc/callback`. The API redeems the
   code at the realm's token endpoint (`eos_core.oidc.exchange_code`), verifies the id token against the
   realm's JWKS (`eos_core.oidc.verify_realm_token`: the realm must be in `EOS_OIDC_REALMS`, checked before
   any network call; RS256, issuer `<EOS_OIDC_ISSUER_BASE>/realms/<slug>`, audience `EOS_OIDC_CLIENT_ID`,
   expiry, `typ: ID` here and `azp` our client when present; keys cached per realm for
   `EOS_OIDC_JWKS_TTL_SECONDS`), maps it to a user (below) and answers like `/auth/login`: the platform's
   own HS256 token. Nothing else in the API changes. `403 no_account` means the realm knows the person and
   identity does not.
4. A realm access token presented directly as a bearer token also works: `eos_core.security.decode_token`
   routes RS256 tokens to the verifier and to `resolve_oidc_claims` here, which returns the platform's
   claim shape (`sub` = identity user id, `org`, `roles` from the user row, `sa` false). Only an access
   token (`typ: Bearer`): an ID token is refused as a bearer token. A slug taken out of `EOS_OIDC_REALMS`
   stops authenticating at once, cached keys or not.

The realm comes from the token's unverified issuer, so the key lookup assumes a forged token: the JWKS is
fetched outside the cache lock with a short timeout (`EOS_OIDC_JWKS_TIMEOUT`, 2 s), an unknown `kid`
refetches at most once per realm per 60 s (key rotation), a failed fetch is remembered for 30 s, and at
most four fetches run at once across realms (beyond that a request is refused, not queued).

User mapping (`application/service.py: user_for_oidc_claims`): the organisation is the one whose slug is
the realm; it must be `active`. The user is found by `(organisation_id, oidc_subject)`; when no user carries
the subject yet, an active user of that organisation with the token's `email` (only with
`email_verified: true`) and no subject is linked to it (event `identity.user.oidc_linked`). After that the
subject is the key, so another realm account with the same email cannot take the user over. A disabled
user is refused. Users must therefore exist in identity (invited through `POST /users` or registration)
before their first sign-in.

### Settings (`config/env.example`, the same in `infra/docker/.env.api`)

| Variable | Meaning |
|---|---|
| `EOS_OIDC_ISSUER_BASE` | Keycloak's public base, e.g. `https://educationos.futureacad.ae/auth`. Empty: OIDC off. |
| `EOS_OIDC_CLIENT_ID` | The public client every realm holds; the audience the API checks. Default `education-os-web`. |
| `EOS_OIDC_REALMS` | Slugs whose realm exists, comma-separated; `*` once tenancy creates realms at approval. |
| `EOS_OIDC_JWKS_TTL_SECONDS`, `EOS_OIDC_HTTP_TIMEOUT` | Key cache lifetime (3600) and code-exchange timeout (5 s). |
| `EOS_OIDC_JWKS_TIMEOUT` | Signing-key fetch timeout, inside a request (2 s). |

### Realm setup for a pilot organisation (manual until `integrations/keycloak`)

`tools/scripts/keycloak-realm.sh <slug> [redirect-uri ...]` does all of this through the Admin REST API
and is safe to re-run (`KEYCLOAK_URL`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` in the environment; the
password is prompted for when unset, never stored and never on curl's command line). The public proxy
serves `/auth/admin/` and the master realm only on the LAN, so run it from the office network or on the
API host with `KEYCLOAK_URL=http://<KEYCLOAK_BIND>:8080/auth`. By hand, in the admin console at
`/auth/admin/` (office network):

1. **Realm**: name = the organisation slug exactly (it is the issuer path and the lookup key); enabled;
   Login tab: *Email as username* on, *Login with email* on, *User registration* off, *Forgot password* on,
   *Verify email* on.
2. **Client** `education-os-web`: OpenID Connect, *Client authentication* off (public client),
   *Standard flow* on, every other flow off; *Valid redirect URIs* `https://<web host>/*`; *Web origins* `+`;
   Advanced: *Proof Key for Code Exchange Code Challenge Method* `S256`. Client scopes: `basic`, `email`
   and `profile` as default (the `openid` scope is implicit; `basic` puts `sub` in the access token),
   nothing optional.
3. **Audience mapper** on that client (Client scopes → `education-os-web-dedicated` → Add mapper → Audience):
   included client audience `education-os-web`, add to access token. Without it the access token's `aud` is
   `account` and the API refuses it; the id token already names the client.
4. **Users**: create with the same email as in identity (or federate the realm with the institution's
   Google / Microsoft / SAML under *Identity providers*; ADR-0006 decision 3). Set a temporary password
   or send the *Update password* required action email.
5. On the API host add the slug to `EOS_OIDC_REALMS` in `infra/docker/.env.api` and
   `docker compose ... up -d` the `api` service.

Check: `curl -s https://<host>/auth/realms/<slug>/.well-known/openid-configuration | head -c 200` shows
the issuer; `curl -s https://<host>/api/v1/identity/auth/oidc/config?slug=<slug>` answers 200.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
