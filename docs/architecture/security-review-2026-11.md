# Security review, November 2026 (v1.0 launch update)

Update of the [October review](security-review-2026-10.md) for the launch checklist item "Security review
filed; open findings assigned" (issue #314). It covers what merged after the October review (its last commit,
30 October 2026, #353) up to `origin/main` at 97ba1f5d (20 November 2026), which includes #665 (terms acceptance) and #554
(platform/integration-hub backend, reviewed on its branch at e227770b and merged during this review; the merged code
is the same).

Reviewer: Claude Code for Faizan, 20 November 2026. Status: in progress; each area is committed as it is reviewed.

## 1. Scope

Security-relevant code new or changed since 30 October, by area:

1. platform/integration-hub (#554): OAuth state, callback verification, the secret store and key rotation,
   the reject limit, SSRF in provider requests, tenant resolution.
2. platform/api-gateway (#363) and its deployment (`infra/`, `tools/scripts/deploy-api-lxc.sh`): rate limits,
   security headers, trusted proxies (`EOS_TRUSTED_PROXIES`, `EOS_FORWARDED_ALLOW_IPS`).
3. Authentication: Keycloak/OIDC (#365), impersonation (#655), `eos_core.security` and `eos_core.oidc`.
4. Tenancy and row-level security: every migration added since October, platform-scope consumers, terms
   acceptance (#665), export and purge (#354, #366).
5. The republish endpoints: `POST /account-links/republish` (student-information, #606),
   `POST /offerings/republish` (academic-management, #651), `POST /registrations/republish`
   (enrolment-registration, #652, open).
6. `eos_core.workflow.submit` (#654).
7. Platform services: documents (#408, #437, #645), notification (#360, #649, #659), workflow (#407, #430, #646),
   billing GST invoices (#541), audit, reporting, search, scheduler, event-bus.
8. Integrations: payment-sbiepay, messaging-providers, digilocker, nad, government-portals,
   external-university-portals, video-conferencing, wearables.
9. Secrets and configuration: `.env` examples, development defaults, `EOS_DEV_MODE` guards.

## 2. Method

Code read at the commits above. A suspected bug is confirmed with a test against that code before it is called a
finding; the table says which findings were confirmed by a test and which by reading only. Severity: critical
(exploitable now, cross-tenant or platform takeover), high (exploitable now within a tenant, or cross-tenant once a
written but unmounted component is mounted), medium, low. "Live" means mounted by
`apps/backend/config/modules.enabled.yaml` on `main`; "latent" means written but not mounted, or behind a setting
the deployment does not use. Every finding names an owner from `.github/CODEOWNERS` (Faizan for cross-cutting
ones). Medium and above have an issue.

## 3. Findings

| ID | Severity | Component | Description | Evidence | Verified | Status | Owner | Fix |
|---|---|---|---|---|---|---|---|---|
| N1 | Low | platform/integration-hub | A callback the adapter answers as a handshake writes an `InboundReceipt` row and commits, with no rejection count or limit. With an adapter whose handshake needs no secret (Zoom's `endpoint.url_validation`, N13), anyone can make the hub write one row per request, bounded only by the gateway's per-address bucket (1200 a minute). No adapter is registered on the live host today (the API image installs only messaging-providers and payment-sbiepay, which declare no `eos.integration_adapters` entry point) | `platform/integration-hub/backend/src/eos_integration_hub/application/inbound.py:298-310` | Reading | Open; noted on #554 | himanshu-rooman | Count handshakes per source like rejections (`_over_limit`), or keep no receipt for a handshake; N13 removes the unsigned handshake |
| N2 | Medium | apps/backend gate, platform/identity | A suspended or archived organisation's users keep working on every platform service until their token expires (12 hours): the entitlement gate checks the organisation's status only for feature modules, and `current_principal` checks only the user's status. Sign-in is refused after a suspension, so only tokens issued before it work. Live | `apps/backend/src/eos_backend/gateway.py:27-28`, `:47-50`; `platform/identity/backend/src/eos_identity/api/deps.py:38-50`; `packages/core/src/eos_core/settings.py:21` | Test: after `PUT /tenancy/admin/organisations/{id}/status` suspended, the admin's old token gets 200 on `GET /identity/users` and `GET /audit/records` and 201 on `POST /billing/subscription/upgrade`, while a feature module answers 403 | Open | faizanrooman | Check the organisation's status in `current_principal` (one cached lookup per request, as the gate does), with an explicit allow-list for what a suspended organisation may still read (its own status, billing) |
| N3 | Medium | platform/tenancy (impersonation), packages/core events | What a super admin does while impersonating is recorded as the impersonated user: only `tenancy.impersonation.started` names the super admin; every later event and audit record carries the user as actor and nothing else, because `events.publish` has no field for it. The reason may be empty. Live | `platform/tenancy/backend/src/eos_tenancy/application/service.py:449-469`; `packages/core/src/eos_core/events.py:36-46`; `platform/audit/backend/src/eos_audit/application/consumers.py:152-160` | Test by the platform-services review agent (not kept): under impersonation the super admin created a user, a chain and approved a request; the outbox events and the audit record name only the organisation admin | Open | faizanrooman | Carry the token's `imp` into the request context and the event envelope (`impersonated_by`), store it in audit, and require a non-empty reason |
| N4 | Low | modules/student-lifecycle/student-information | `POST /account-links/republish` publishes one `person.account-linked` per linked person of the organisation, synchronously and with no throttle, and `admissions-staff` and `registrar` hold the key it needs (`person:write`), not only the admin. Repeated calls fill the outbox and every consumer with copies (harmless to data: consumers apply by `occurred_at`, but each call is O(persons) events). Organisation scoping is correct | `modules/student-lifecycle/student-information/backend/src/eos_student_information/api/router.py:129-135`; `application/service.py:345-361` | Reading | Open | praveen-rooman | Require an admin-only key (or `org-admin`) for the backfill and refuse a second run within a cool-down (store the last run per organisation) |
| N5 | Low | modules/academics/academic-management | `POST /offerings/republish` publishes four events per offering and section of the whole organisation, synchronously, with no throttle; `department-admin` holds the key (`offering:write`) and can trigger the organisation-wide backfill. Scoping is correct (`repo.q`) | `modules/academics/academic-management/backend/src/eos_academic_management/api/router.py:249-253`; `application/service.py:1026-1056` | Reading | Open | shivanisinghrooman-09 | As N4: an admin-only key and a cool-down per organisation |
| N6 | Medium | packages/core workflow hook, platform/workflow | The outcome events `workflow.request.approved` / `rejected` identify the record only by `entity_type` and `entity_id`, and anyone holding `workflow:request:create` (students and faculty do) can create a request with any `entity_type`, `entity_id`, chain and `context` through `POST /workflow/requests`. `eos_core.workflow.submit` tells modules the outcome "carries the same entity_type and entity_id", so a module that acts on an approval by matching those would act on a request a student made up. No module consumes the outcome yet. Latent | `packages/core/src/eos_core/workflow.py:73-75`; `platform/workflow/backend/src/eos_workflow/api/router.py:55-60`, `:152-170`; `platform/workflow/contracts/permissions.yaml` (student, faculty: `workflow:request:create`) | Reading | Open | faizanrooman | Reserve entity types per module (`<module>.<type>`): `submit()` stamps the calling module, `POST /requests` refuses a reserved prefix; and document that a consumer matches the outcome's `request_id` to the id `submit()` returned |
| N7 | Medium | platform/billing | `POST /billing/webhooks/payment` takes no token and checks no signature (its docstring says the adapter verified it, but nothing calls it from an adapter): anyone holding a pending upgrade's `reference` (handed to the organisation admin in the upgrade response and `payment_url`) activates the plan without paying, and a "paid" GST invoice is written. Latent while `BILLING_PAYMENT_ADAPTER=none` (the deployment's value, N8); High the day an adapter is configured | `platform/billing/backend/src/eos_billing/api/router.py:133-139`; `application/service.py:145-153` | Test: with the adapter setting changed from `none`, an organisation admin's upgrade to premium is pending, then an unauthenticated `POST /billing/webhooks/payment {"reference": ...}` answers 204 and the subscription is premium and active | Open | faizanrooman | Verify an HMAC signature over the body with a webhook secret, and the amount and plan, before `confirm_payment`; or drop the route and confirm from payment-sbiepay's `payment.succeeded` event |
| N8 | Medium | platform/billing | With `BILLING_PAYMENT_ADAPTER=none` (what `deploy-api-lxc.sh` writes), any organisation admin's `POST /billing/subscription/upgrade` activates any published plan, premium included, at once and writes a "paid" GST tax invoice that uses a number from the real series. Live; may be intended for the pilot, but it gives away paid plans and issues tax invoices for money never received | `platform/billing/backend/src/eos_billing/application/service.py:122-139`; `tools/scripts/deploy-api-lxc.sh:107` | Existing test `apps/backend/tests/test_billing_invoices.py` relies on it | Open | faizanrooman | Outside dev mode, refuse a paid plan when no adapter is configured (or route it to super-admin approval), and never number an invoice that was not paid |
| N9 | Medium | platform/documents, platform/tenancy (purge) | Purging an organisation deletes its `documents_document` rows but not the stored files under `<organisation>/` in object storage: documents has no consumer of `tenancy.organisation.purged` (only search and audit have one) and the export lists references only. The purge then claims an erasure that did not happen. Latent: documents is not mounted | `platform/tenancy/backend/src/eos_tenancy/application/service.py:584`; `application/tables.py:103`; no `organisation.purged` handler under `platform/documents/` | Test by the platform-services review agent (not kept): after a purge the row is gone and the stored bytes remain | Open | himanshu-rooman | A documents consumer of `tenancy.organisation.purged` that deletes the organisation's prefix and pending uploads, or block the purge until storage is cleared |
| N10 | Low | platform/reporting | Whether a report is financial is read from the definition's `category`, not from the metrics it reads: an organisation admin can define a custom report whose code is a financial metric (`finance.fees_collected`) with category `academic`, and faculty, who hold only `reporting:report:read`, can then run it and see the figure | `platform/reporting/backend/src/eos_reporting/application/service.py:39-46`, `:409`; `api/router.py:189` | Test by the platform-services review agent (not kept): faculty 404 on the system fee report, 200 with the total on the relabelled one | Open | himanshu-rooman | Decide sensitivity from the metrics (`metrics.BY_KEY[k].category`), and refuse a custom code naming a financial metric unless its category is financial |
| N11 | Low | platform/documents | The presigned upload is not bound to a content type or length (checked only at `/confirm`), and unconfirmed uploads are never swept, so any holder of `documents:document:write` (students, faculty) can park large objects indefinitely; a deleted document keeps its filename and title, listable with `?status=deleted`; `department-admin` holds `read-any` over the whole organisation. Latent: not mounted | `platform/documents/backend/src/eos_documents/infrastructure/storage.py:81-92`; `application/service.py:405`; `contracts/permissions.yaml:7-21` | Reading | Open | himanshu-rooman | Sign the content type and a length range into the upload, sweep stale pending uploads, blank the filename and title on delete, narrow `read-any` |
| N12 | Low | platform/workflow | No department dimension: any `department-admin` can read and decide any request whose chain has a department-admin step, from any department of the organisation | `platform/workflow/backend/src/eos_workflow/application/service.py:254-290` | Reading | Open | himanshu-rooman | Add a department to steps and requests and match on it |

## 4. Reviewed, no findings

**platform/integration-hub (#554).** Now mounted in the host (`platform:` list); its routes are platform routes, so the
entitlement gate lets the OAuth callback and `/inbound/...` through and each route checks its own key (covered by
`apps/backend/tests/test_platform_permissions.py`). No adapter is registered on the live host yet, so every inbound
path answers 404 there. Checked:
- OAuth state (`application/authorisation.py:119-177`, `348-423`): 32-byte random state stored only as a SHA-256
  hash, PKCE S256 with the verifier encrypted under the hub key and the state hash as associated data, single use by one
  conditional `UPDATE` (`claim_state`), bound to the browser by an HttpOnly, Secure, SameSite=Lax cookie compared in
  constant time, refused when a signed-in caller is not the person who started it, and spent on any mismatch. The
  return URL is checked against `INTEGRATION_HUB_ALLOWED_RETURN_HOSTS` (no userinfo, https only off localhost).
- Callback verification (`application/inbound.py:270-381`): every request is verified by the adapter over the raw
  body before anything is processed; an unverified one is never processed; the body limit is checked before and while
  reading; dedupe is per connection; a raw body is kept only encrypted.
- Tenant resolution (`inbound.py:398-430`): a connection key in the URL is looked up by hash; an app-level callback
  resolves only to a connection of the same adapter, or to exactly one active account link (two organisations with
  the same provider account resolve to nobody). Whether the adapter's own `resolves_to` can be trusted is the
  adapter's verification (see N13 to N15).
- Reject limit (`inbound.py:127-238`): past the limit, rejections are still answered and verified but nothing is
  written; a signed callback is never refused because of someone else's junk. Handshakes are not counted (N1).
- Secret store and key rotation (`infrastructure/secrets.py`): AES-256-GCM with the reference as associated data, a
  key id per blob, the previous key accepted only while rotating, files 0600 in 0700 directories written atomically;
  outside dev mode a missing or malformed `INTEGRATION_HUB_SECRET_KEK` refuses (no fallback key), and the `env`
  backend is refused; no value is logged or put in an exception.
- SSRF: the hub makes no outbound request itself; adapters do, from connection settings an organisation admin
  enters. The hub has no shared address guard for those settings (see N16, Jitsi).

**platform/api-gateway (#363) and its deployment (#590, #663).** Checked: `X-Forwarded-For` is believed only from
`EOS_TRUSTED_PROXIES` (loopback by default) and read from the right, so a client cannot pick its bucket
(`application/limiter.py:425-441`); IPv6 is keyed by /64; the sign-in body is read at most 16 KiB and a larger one
answers 413, so padding cannot dodge the per-account bucket; a refused sign-in costs an attempt and nothing else
does; an invalid token is anonymous (address bucket); refusals are given back to buckets already charged. Security
headers go on every response including refusals (`api/middleware.py:219-244`). `deploy-api-lxc.sh:116-131` writes
the proxy's address into both `EOS_TRUSTED_PROXIES` and uvicorn's `EOS_FORWARDED_ALLOW_IPS` and replaces a loopback
value; uvicorn then rewrites the peer to the client, and the gateway keys on that peer, which it does not trust, so
the two settings agree. The in-process buckets count per worker (documented in the scale runbook); Compose runs one
worker unless `EOS_API_WORKERS` is set. October's S11 (port 8000 published on every interface,
`infra/docker/docker-compose.api.yml:149-150`) is unchanged; a direct LAN caller still cannot forge its address,
because only the proxy's address is trusted. No new finding.

**Authentication (#365, #655).** `eos_core.security.decode_token` picks the verification path by algorithm, and each
path accepts only its own (`HS256` against the secret, `RS256` against the realm's keys), so neither `alg: none` nor
an HS256 token signed with a realm's public key passes. A realm token (`eos_core/oidc.py:283-318`) is refused before
any network call unless its issuer is one of our realms and the realm is enabled (`EOS_OIDC_REALMS`); then
signature, issuer, audience, expiry, `typ` (an ID token is not a bearer token) and `azp`; the JWKS fetch is bounded
(timeout, one refetch per realm a minute, four at once, failures remembered). Identity maps a realm token to a user of
the realm's own organisation only, checks that organisation's status on every request, and links by email only when
Keycloak says it is verified and the user has no subject yet (`identity/application/service.py:227-262`); the
super admin never signs in through OIDC. Impersonation (#655): only `platform:organisations:impersonate` (super
admin), only a user of that organisation, a 60-minute token with `sa` false and without `service`; attribution is N3.
Tokens still cannot be revoked (October S8, accepted).

**Tenancy and row-level security.** Every migration chain on `main` (the 41 enabled modules, the 11 enabled platform
services, the two enabled integrations, and the unmounted documents, search and six integrations) was applied to an
empty PostgreSQL 16 database as the deploy does (`infra/docker/migrate.sh`, then `alembic upgrade head` for the rest),
and the catalogue was queried: 443 tables, of which 380 carry `organisation_id`, and every one of those has row-level
security enabled and forced and the standard `tenant_isolation` policy on `app.organisation_id`. The tables without
`organisation_id` are the Alembic version tables, `billing_plan`, `billing_invoice_counter` (exempted in its
migration) and `tenancy_organisation`, as in October. Consumers that run per event (`library`, `budget-grants`,
`fees-accounts` and the rest) refuse to run inside `platform_scope` and switch to the event's organisation; the
modules' `platform_scope` uses since October are scheduled sweeps. Terms acceptance (#665): registration is refused
without `accepted_terms: true`, and the version, time and accepting user are recorded server-side. Export and purge
(#354, #366): every route needs a `platform:` key; the purge finding is N9.

**Republish endpoints.** All three filter by the caller's organisation (`student-information` explicitly,
`academic-management` through `repo.q`, `enrolment-registration` explicitly in #652) and change no state; consumers
apply by occurred time, so a republish does not roll anything back. Abuse by repetition: N4, N5, and the same note
on #652 (`registration:manage`).

**`eos_core.workflow.submit` (#654).** It skips `workflow:request:create` by design: the caller is a module acting
for its own user, and `requested_by` must be that user (the self-approval rule and the per-requester idempotency key
depend on it). No module calls it yet. The risk is the reverse direction, N6.

**Platform services** (reviewed with the help of a sub-agent that wrote and ran its tests against `main` at
9178745c; N2 was re-run for this report).
- documents (#408, #437, #645): every query filters by organisation; object keys are built from server ids
  (`<organisation>/...`), never from a filename; download links only after a visibility check, 900 s, as an
  attachment; only the uploader confirms or versions; a confirmed file cannot be overwritten. Findings N9, N11.
- notification (#360, #649, #659): `string.Template` (no code runs) with organisation overrides limited to declared
  variables and none for secret-bearing templates; one-line subjects and checked addresses (no header injection);
  plain-text bodies; logs carry no address, token or provider error text; recipients by user id must be active
  members of the same organisation; sending over HTTP needs the `service` role.
- workflow (#407, #430, #646): requesters cannot approve, reject or delegate their own requests; every lookup is
  organisation-scoped; delegation only to active members holding the approve key; the pending queue needs the approve
  key; decisions are row-locked. Findings N6, N12.
- billing GST (#541): profiles and invoices tied to the caller's organisation, admin routes need `platform:` keys,
  invoice numbers from a row-locked counter with a unique constraint. Findings N7, N8.
- audit (#406, #434, #455): no update or delete route, the database role cannot delete, organisation callers pinned
  to their own organisation, a super admin's cross-organisation read is itself recorded, secrets and contact details
  dropped from payloads.
- reporting (#409, #433, #452): no SQL from user input, every query filtered by organisation, CSV cells guarded
  against formulas. Finding N10.
- search (#551, not mounted): organisation and permission filters cannot be left out of a query, filter fields are
  allow-listed, cursors are signed and bound to the user and query, `organisation_id` in a query is refused.
- scheduler (#357) and event-bus (#436): organisation callers see and change only their own; platform jobs and relay
  health need the super admin; only dead-lettered events can be replayed.
