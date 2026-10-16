# ADR-0006: OpenID Connect provider

- **Status:** accepted
- **Date:** 2026-10-12
- **Deciders:** Faizan (lead), with platform/identity (Himanshu) and infrastructure (Srujan)

## Context
Education OS signs users in with an email and password held by platform/identity (ADR-0005). That is
enough for trial organisations, but institutions arrive with their own identity: Google Workspace for
Education, Microsoft Entra ID, or an on-premise directory, and they expect single sign-on and the
ability to switch off an account in one place. The platform also needs one consistent token format
for the API gateway, the per-module services and the integrations.

Three questions had to be settled: which standard, which provider, and where the user record lives.

## Decision
1. **OpenID Connect (OIDC) on top of OAuth 2.1 is the only sign-in protocol the platform speaks.**
   SAML institutions are brokered through the provider, never implemented by us.
2. **Keycloak, self-hosted next to the API, is the OIDC provider.** It runs as one more service in
   `infra/docker/docker-compose.api.yml` on the Docker host, with its own Postgres database, behind the
   same public reverse proxy at `https://educationos.futureacad.ae/auth/`. One Keycloak *realm* per
   organisation, created by platform/tenancy when an organisation is approved; the realm name is the
   organisation slug.
3. **Institutional identity is brokered, not re-implemented.** Each realm can be federated with the
   organisation's Google, Microsoft or SAML identity provider through Keycloak's identity brokering.
   An organisation that has none keeps Keycloak's own username and password.
4. **platform/identity stays the system of record for the user, roles and organisation membership.**
   Keycloak authenticates; identity authorises. The access token carries `sub`, `org` (the realm's
   organisation id) and nothing else about roles; `current_principal` looks the user up by `sub` and
   builds permissions from the role catalogues as today. Keycloak's own roles and groups are not used.
5. **The existing password login remains until the provider is live, and afterwards for the platform
   super admin.** Organisations are migrated realm by realm; a user is created in the realm on first
   invite, with a password reset email, so no password hashes move.

## Consequences
- The API accepts two token issuers during the migration: its own HS256 tokens (today) and Keycloak's
  RS256 tokens verified against the realm's JWKS. `eos_core.security.decode_token` grows an issuer
  check; nothing in the routers changes because they depend on `Principal`, not on the token.
- The web shell gets a "Continue with your institution" button that starts the authorization code
  flow with PKCE against the organisation's realm, resolved from the slug typed on the sign-in page.
- One more stateful service to run, back up and upgrade. Srujan owns its deployment; it is on the
  same host as the API and uses the same backup routine as the API's Postgres.
- Realm creation, identity-provider federation and user invitation become tenancy and identity
  work (Keycloak Admin REST API through an `integrations/keycloak` adapter). Until that lands, a
  realm is created by hand for pilot institutions.
- Offline development does not need Keycloak: `EOS_DEV_MODE` keeps the password login, and the test
  suites keep using it.

## Alternatives considered
- **Hosted providers (Auth0, Clerk, Okta, Firebase Auth).** Fastest to start, but per-active-user
  pricing across many institutions is unpredictable, user data would sit outside the deployment,
  and institutions in regulated regions ask where their directory data goes. Rejected.
- **Implement OIDC ourselves in platform/identity (for example with Authlib).** Full control, no new
  service, but we would own password policy, MFA, session management, brokering to Google,
  Microsoft and SAML, and the security review of all of it. That is a product in itself. Rejected.
- **Ory Hydra + Kratos, or Authentik.** Capable and lighter than Keycloak in places, but Keycloak has
  the broadest SAML and institutional brokering support, the largest operator community, and is what
  most universities already run or know. Keycloak chosen; this can be revisited if its footprint becomes
  a problem on the current host.
- **Keep passwords in platform/identity only, add Google and Microsoft sign-in directly.** Covers the
  two common cases but not SAML, and spreads provider-specific code through identity. Rejected.
