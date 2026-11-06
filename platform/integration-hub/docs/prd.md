# integration-hub: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Srujan · Kind: platform · Tier: core · Status: draft for review
Sprint v1.0 integrations (lead's decision, 5 Nov 2026): the hub and all six adapters ship in v1.0 by 19 Nov.

## Purpose

The one place Education OS meets the outside world, so that no module ever talks to a vendor.

`docs/architecture/ARCHITECTURE.md` puts adapters behind `platform/integration-hub`, and `integrations/README.md` sets
the swap rule: replacing a provider means adding an adapter and changing configuration, never changing a module. Two
adapters predate this contract and each carries its own port (`messaging-providers` has `OutboundMessaging`;
`payment-sbiepay` proposes its API as the payment port). This PRD defines the hub those adapters were waiting for:

1. **Ports**: one capability interface per kind of integration, in `contracts/ports/`. A module calls a port; the hub
   runs the call on the organisation's enabled connection for that port; an adapter speaks to the provider.
2. **The hub's own API** (`contracts/openapi.yaml`): connections per organisation, credentials kept in a secret store
   and never in the database, mock, sandbox and live modes, OAuth for organisations and for people, provider callbacks
   with signature verification, health, and a delivery log with retries.
3. **Events** (`contracts/events.yaml`): connection and delivery events, and port events normalised from whatever
   provider answered, so a consumer subscribes to a port and never to a vendor.

This PR is contracts only: no code, migrations or screens.

## What it is not

| Not this | That belongs to |
|---|---|
| Talking to a provider's API, its formats and its quirks | the adapter in `integrations/<adapter>` |
| Deciding *when* to issue a certificate, create a meeting or file a return | the consuming module (examinations, lms, regulatory-reports, ...) |
| Storing what came back (results, attendance, readings) as the module's own record | the consuming module, from the port's output or event |
| Sending email, SMS and WhatsApp | `platform/notification` through `messaging-providers` (an existing port, open question 1) |
| Payments | `payment-sbiepay` (open question 1) |
| Generic file import and export for users (CSV of students) | each module; `platform/reporting` for exports |
| A general-purpose API gateway for third parties calling us | `platform/api-gateway` |

## Users

| Who | Needs | Through |
|---|---|---|
| Org admin (`org-admin`) | Connect the institution's Zoom or Microsoft 365, enter its DigiLocker issuer keys, test in sandbox, go live, see what failed and retry | `/connections`, `/deliveries` |
| Every person (`member`) | Link their own Garmin, Polar or DigiLocker account, see the link and disconnect it | `/me/account-links` |
| Super admin | See across organisations which providers are in which mode and healthy, and which platform credentials are missing | `/platform/overview` |
| Modules (examinations, lms, regulatory-reports, athlete-performance, ...) | Call a port and get a result or an event, without knowing the provider | `packages/sdk` `integrations.invoke` |
| Adapters | Be found, be given the context and secrets for one call, verify and parse callbacks | entry point `eos.integration_adapters` and `contracts/ports/adapter.yaml` |

## Concepts

| Term | Meaning |
|---|---|
| **Port** | A capability interface, versioned, in `contracts/ports/<port>.yaml`. Operations are `sync` (answer now) or `async` (a delivery id now, the outcome as an event). |
| **Adapter** | A module in `integrations/` that implements one or more ports for one or more providers, plus `contracts/ports/adapter.yaml`. Found by entry point, never imported. |
| **Provider** | One outside system an adapter speaks to: `zoom`, `teams`, `digilocker`, `garmin`, `aishe`. |
| **Connection** | One organisation's configuration of one adapter, provider and port: settings, credential references, mode, enabled flag, health. |
| **Mode** | `mock` (recorded responses, no network), `sandbox` (the provider's test environment) or `live`. |
| **Account link** | One person's authorisation at a provider whose link scope is `person` (their Garmin, their DigiLocker wallet). Tokens in the secret store. |
| **Delivery** | One row of the log per port operation (outbound) or provider callback (inbound), with attempts and outcome. |

## The ports

| Port | Adapter | Providers in v1.0 | Consumers (proposed) | What it does |
|---|---|---|---|---|
| [certificate-issuance](../contracts/ports/certificate-issuance.yaml) | digilocker | DigiLocker (issuer and requester) | examinations, student-information, admissions | Put issued documents in the holder's wallet; replace, withdraw; answer pull requests; fetch or verify a person's documents with consent |
| [academic-records](../contracts/ports/academic-records.yaml) | nad | NAD (on DigiLocker), ABC / APAAR | examinations, student-information, enrolment-registration | Lodge awards and credits keyed by APAAR id; verify an APAAR id; CSV package when there is no API |
| [regulatory-submission](../contracts/ports/regulatory-submission.yaml) | government-portals | AISHE, NIRF, NAAC (IIQA, SSR, AQAR, DVV) | regulatory-reports, iqac-accreditation | Prepare the portal's own package, validate, record the manual filing; `submit` for the day a portal has an API |
| [meetings](../contracts/ports/meetings.yaml) | video-conferencing | Zoom, Microsoft Teams, Webex, Jitsi (self-hosted) | lms or timetable-attendance (lms LQ8), selection-process, alumni | Create, change, cancel; join links per person; started, ended, attendance, recordings |
| [wearable-data](../contracts/ports/wearable-data.yaml) | wearables | Garmin, Polar, Fitbit (Google Health API), Strava | athlete-performance, sports-nutrition-health | Athlete links their device account; daily summaries, activities, sleep normalised; read for an athlete |
| [inter-institution-records](../contracts/ports/inter-institution-records.yaml) | external-university-portals | File exchange (PDF, CSV), EMREX ELMO XML, Europass EDC | examinations, enrolment-registration, student-information, admissions | Export a transcript in a partner's format and send it; import a partner's file for review |

Every adapter also implements [adapter.yaml](../contracts/ports/adapter.yaml): `capabilities`, `healthcheck`, the
OAuth steps, `verify_inbound`, `parse_inbound` and `handle_provider_request`, with one error vocabulary
(`not_configured`, `auth_failed`, `consent_required`, `invalid_request`, `not_found`, `conflict`, `rejected`,
`unsupported`, `manual_action_required`, `throttled`, `transport_unavailable`, `provider_error`), each with a fixed
retryable flag. A module handles a failure the same way whoever the provider is.

**No API is a first-class answer.** AISHE, NIRF and NAAC have no API an institution can use; NAD's upload API and ABC's
are not public. The ports for them are built around a package a person files, and `manual_action_required` says so
rather than pretending something was sent. An adapter gains an API path later without a port change.

## How a module uses a port

```
result = sdk.integrations.invoke(
    port="meetings", operation="create_meeting",
    input={...},                       # as contracts/ports/meetings.yaml defines it
    idempotency_key="lms:class-session:<id>",
    caller_reference="<class_session_id>",
)
```

1. The SDK passes the call in process to the hub's application layer, as the calling module and organisation (the
   request's tenant). The module has already checked its own user's permission; the hub checks that the organisation
   has an **enabled** connection for the port, else `not_configured`.
2. The hub writes a delivery row (`queued`), resolves the connection's secrets from the secret store into memory, and
   calls the adapter with the context in `adapter.yaml`.
3. **Sync** operations return the adapter's result to the caller within `INTEGRATION_HUB_SYNC_TIMEOUT_S`; a retryable
   failure is returned as is, and the caller decides. **Async** operations return the delivery id at once and run in an
   `arq` job; the outcome is `integration-hub.delivery.succeeded`, `.failed` or `.manual-action-required`, matched by
   `caller_module` and `caller_reference`, plus the port event (e.g. `integration-hub.certificate.issued`).
4. The same idempotency key within `INTEGRATION_HUB_IDEMPOTENCY_WINDOW_DAYS` returns the first delivery, never a second
   call to the provider.
5. Where an organisation has two enabled connections for a port with different providers (Zoom for one department,
   Teams for another), the input names `provider`; with one, it is chosen for the caller.

`packages/sdk` has no integrations client yet; adding `integrations.invoke` is part of the hub's build (open question 2).

## Connections and modes

- A connection starts **disabled** in `mock` or `sandbox`. Enabling needs every credential the provider names and a
  healthcheck that is not `auth_failed`.
- `mock` uses the adapter's recorded responses with no network. It is refused unless `INTEGRATION_HUB_ALLOW_MOCK` is
  true, which only development and demo deployments set, so a production organisation never "issues" a certificate to
  a fixture.
- `sandbox` uses the provider's test environment with test credentials.
- **Going live** (`POST /connections/{id}/mode`) needs the separate key `integration-hub:connection:go-live`, every live
  credential, a healthy check in the same request, and `confirm_live`. It publishes
  `integration-hub.connection.mode-changed`. Deliveries queued in one mode are never replayed in another.
- **The launch does not wait for an agency** (lead's decision). DigiLocker, NAD and the government portals stay in
  sandbox, or on their manual path, until the agency approves the institution; switching to live is then a credential
  entry and one request, with no release.
- One enabled connection per organisation, port and provider. `external-university-portals` uses one connection per
  partner institution.

## Credentials and the secret store

- **Never in the database.** A connection row holds, per credential name, a reference
  (`secret://integration-hub/<organisation_id>/<connection_id>/<name>`), a fingerprint (first 8 hex characters of its
  SHA-256), who set it and when, and its expiry. The value lives in the secret store.
- **Backends** (`INTEGRATION_HUB_SECRET_BACKEND`), behind one small interface (`put`, `get`, `delete`, `rotate_kek`):
  - `file` (the v1.0 default): one file per secret on a volume outside the database and outside backups of the
    database, mode 0600, each value encrypted with AES-256-GCM (`cryptography`, on the approved stack) under a key
    from `INTEGRATION_HUB_SECRET_KEK`. `INTEGRATION_HUB_SECRET_KEK_PREVIOUS` lets the key be rotated without downtime.
  - `env` (read only): for development, values from environment variables.
  - A vault service (OpenBao or HashiCorp Vault over `httpx`) is the better home once there are many per-person
    tokens; it is a new piece of infrastructure, so it is open question 3, not part of this contract.
- **Write-only API.** `PUT /connections/{id}/credentials/{name}`; no endpoint returns a value, masked or otherwise. The
  audit record and the event carry the name and fingerprint only.
- **Platform credentials** (Rooman's own DigiLocker partner app, the Zoom Marketplace app, the Garmin and Strava
  developer apps) are set once per deployment as the adapter's environment variables, never per organisation, and are
  visible to the super admin only as present or missing.
- **Tokens from OAuth** (an organisation's Zoom tokens, a person's Garmin tokens) are written by the callback and
  refreshed by a scheduled job `INTEGRATION_HUB_TOKEN_REFRESH_LEAD_S` before they expire. A refresh that fails with
  `auth_failed` marks the connection or link `expired` and tells the owner.
- Secrets are resolved into memory for one call and never logged, put on an event, written to a delivery, or kept in
  an exception message. The adapter tests from `messaging-providers` (no secret in `repr()`, a log line or an error)
  apply to every adapter.

## Authorisation (OAuth)

- **Organisation scope** (Zoom, Webex, Microsoft 365): an org admin starts `POST /connections/{id}/authorise`, approves
  at the provider (as the tenant's admin where the provider requires it), and returns to `GET /oauth/callback/{adapter}`.
- **Person scope** (Garmin, Polar, Fitbit, Strava, a DigiLocker wallet): the person starts `POST /me/account-links`. Our
  page shows the purpose and what will be shared before the redirect. Nobody links an account for someone else.
- PKCE (S256) wherever the provider supports it (DigiLocker requires it). `state` is a random single-use value, stored
  server-side with the verifier, bound to the organisation, the connection or link and the person, and expiring after
  `INTEGRATION_HUB_OAUTH_STATE_TTL_S`. The redirect back goes only to hosts in `INTEGRATION_HUB_ALLOWED_RETURN_HOSTS`.
- Disconnecting revokes at the provider (`revoke_authorisation`), deletes the tokens, and publishes
  `integration-hub.account-link.revoked`, on which the adapter deletes the data collected under the link.

## Inbound: webhooks and provider requests

All provider callbacks arrive at the hub, never at an adapter's own route:

| Route | For |
|---|---|
| `POST/GET /inbound/{adapter}` | One URL per application for every tenant: Strava, Polar, Garmin, a Zoom Marketplace app |
| `POST/GET /inbound/{adapter}/{connection_key}` | A webhook an organisation registered with its own account: Zoom, Graph, Webex, BigBlueButton |
| `POST /inbound/{adapter}/{connection_key}/{channel}` | A provider waiting for an answer: DigiLocker's Pull URI and Pull Doc requests |

`connection_key` is a random 32-byte token per connection, rotated with the webhook secret, so a URL reveals nothing.

1. Refuse a body over `INTEGRATION_HUB_INBOUND_MAX_BYTES`. Keep the **raw** body: signatures are computed over bytes,
   not re-serialised JSON.
2. The adapter's `verify_inbound` decides: **accept**, **reject** (with the status the provider expects, 401 by default),
   or **handshake** (Zoom `endpoint.url_validation`, Strava `hub.challenge`, Graph `validationToken`, Fitbit `verify`).
   A request that cannot be verified is rejected, logged as `rejected_inbound`, and never processed.
3. Deduplicate on the provider's event id; a redelivery is acknowledged and ignored.
4. **Acknowledge before processing.** Providers give 2 to 10 seconds (Strava 2 s, Zoom 3 s, Fitbit 5 s, Graph 3 s for
   a 2xx, 10 s for validation). Processing (`parse_inbound`, a follow-up fetch for ping-only webhooks, events) runs in
   a job and is logged as an inbound delivery.
5. Provider requests are answered synchronously by `handle_provider_request` from the adapter's own records within
   `INTEGRATION_HUB_PROVIDER_REQUEST_TIMEOUT_S`; the answer body is not kept.
6. Raw bodies are kept for `INTEGRATION_HUB_INBOUND_RAW_RETENTION_DAYS` for support, encrypted like delivery payloads,
   then deleted.

## Delivery log and retries

- Every outbound operation and every inbound callback is a delivery: port, operation, connection, caller module and
  reference, idempotency key, status, attempts, last error code, provider reference, timings. **Never the payload in
  the log or the API.**
- The input of an async operation is kept, encrypted under the secret-store key, only so it can be retried, and is
  deleted `INTEGRATION_HUB_DELIVERY_PAYLOAD_RETENTION_DAYS` after the delivery ends. The row itself is kept
  `INTEGRATION_HUB_DELIVERY_LOG_RETENTION_DAYS`.
- Retries only for retryable error codes. Exponential backoff with full jitter from `INTEGRATION_HUB_RETRY_BASE_S` up to
  `INTEGRATION_HUB_RETRY_MAX_S`, at most `INTEGRATION_HUB_RETRY_MAX_ATTEMPTS`; a provider's `retry_after_s` wins when
  longer. With the defaults (30 s base, 8 attempts, 6 h cap) a delivery is given up after about a day.
- Exhausted retries move the delivery to `dead_lettered`, publish `integration-hub.delivery.failed` with
  `dead_lettered: true`, and tell the org admins. `POST /deliveries/{id}/retry` tries again with the same idempotency
  key.
- A disabled connection keeps its queue; deliveries older than `INTEGRATION_HUB_QUEUE_EXPIRY_HOURS` fail as
  `not_configured`.
- Throttling is per connection and provider: when an adapter reports `throttled`, the hub holds that connection's queue
  until the retry time instead of spending every queued item's attempts.

## Health

- `healthcheck` runs every `INTEGRATION_HUB_HEALTH_INTERVAL_MIN` minutes for every enabled connection (through
  `platform/scheduler`), on demand (limited per hour), and before enabling or going live. It never creates, sends or
  changes anything at the provider.
- A transition publishes `integration-hub.connection.health-changed` once; `unreachable` and `auth_failed` notify the
  org admins. A credential or token known to expire within 14 days notifies them once a day.

## Personal data (DPDP Act 2023)

The hub moves personal data to providers; most of it is students', and some is health data.

- **Purpose and consent.** Organisation-scope integrations (issuing a certificate, a class meeting) act for the
  institution under its own lawful basis; the consuming module owns that. Person-scope links (devices, a person's
  wallet) start only from the person, with the purpose shown, and end when the person disconnects.
- **Minimum data.** Ports carry what the provider needs and no more; a mobile number used to find a wallet account is
  not stored. Events never carry names, contact details, documents or readings.
- **Erasure.** Revoking a link deletes its tokens and, through the event, the data collected under it. Delivery
  payloads and raw callbacks are deleted on short retention.
- **Where data goes.** Each adapter PRD names where its provider keeps data and what is in India. Going live is a
  separate permission and an event, so the moment real data starts to leave is visible and audited.
- **Audit.** Every connection change, credential set (name and fingerprint), mode change, link and revoke, manual
  retry and every inbound rejection writes an audit record through `packages/sdk`.

## Data model (summary)

Own schema `integration_hub`; every table has `organisation_id` with row-level security, except the adapter registry,
which is per deployment.

| Entity | Key fields |
|---|---|
| adapter_registry (per deployment) | adapter, version, ports, providers (from `describe()`), installed_at |
| connection | id, organisation_id, adapter, provider, port, mode, enabled, display_name, settings (jsonb, non-secret), connection_key_hash, authorised, health_status, health_detail, health_checked_at, expires_at |
| connection_credential | organisation_id, connection_id, name, secret_ref, fingerprint, source (admin, oauth), set_by, set_at, expires_at |
| account_link | id, organisation_id, connection_id, person_id, port, provider, provider_subject, status, purpose, granted_scopes, secret_ref, linked_at, expires_at, last_synced_at, revoked_at, revoke_cause |
| oauth_state | state_hash, organisation_id, connection_id or account_link_id, person_id, code_verifier (encrypted), return_url, expires_at, used_at |
| delivery | id, organisation_id, direction, connection_id, port, operation, caller_module, caller_reference, idempotency_key, status, attempts, next_attempt_at, last_error_code, provider_reference, payload_encrypted (nullable, purged), created_at, completed_at |
| delivery_attempt | organisation_id, delivery_id, attempt, started_at, duration_ms, outcome, error_code, provider_code |
| inbound_receipt | id, organisation_id (once known), adapter, connection_id, dedupe_key, verdict, raw_body_encrypted (purged), received_at |

An app-level callback arrives before its tenant is known: the receipt is written by the hub's platform role and gets
its `organisation_id` when `verify_inbound` names the connection; one that names none is rejected.

## Events

See `contracts/events.yaml`. The hub's own: `connection.created`, `.updated`, `.authorised`, `.credentials-rotated`,
`.mode-changed`, `.enabled`, `.disabled`, `.health-changed`; `account-link.connected`, `.revoked`;
`delivery.succeeded`, `.failed`, `.manual-action-required`. Port events: `certificate.issued`, `.withdrawn`, `.pulled`;
`academic-record.submission-changed`; `regulatory-package.prepared`, `.submitted`; `meeting.started`, `.ended`;
`meeting-attendance.received`; `meeting-recording.available`; `wearable-data.received`;
`inter-institution-record.exchanged`. All prefixed `integration-hub.`. Payloads carry ids, keys and statuses only.

Real-time `participant_joined` / `participant_left` from the meetings port are not published as events in v1.0: they
are high volume and attendance comes complete from the report. The hub records them for the attendance fallback only
(open question 6).

## Permissions

See `contracts/permissions.yaml`. `org-admin` holds every organisation key; `member` holds `integration-hub:self:link`;
`super-admin` holds the overview. No person needs a hub key for a module to use a port on their behalf.

## Configuration

`config/env.example`, every key prefixed `INTEGRATION_HUB_`: public base URL for callbacks, secret backend, directory
and key, mock switch, allowed return hosts, OAuth state lifetime, inbound size and provider-request timeout, sync
timeout, idempotency window, retry schedule, queue expiry, retention periods, health interval and run limit, token
refresh lead time. Each adapter has its own `config/env.example` for its platform credentials and endpoints.

## v1.0 plan (to 19 November)

| Step | What |
|---|---|
| This PR | Ports and hub contracts reviewed |
| Adapter contract PRs | One per adapter, each depending on this one |
| Hub build | Schema and RLS, secret store (`file`), connections and credentials API, OAuth callback, inbound routes, delivery log with retries, health job, `sdk.integrations.invoke`, mock mode |
| Adapter builds | Against each provider's sandbox, or a recorded mock where none exists (NAD, ABC, the government portals) |
| Live | Per organisation, when the agency or provider approves; no release needed |

## External dependencies (summary)

Each adapter PRD lists what Rooman must apply for, with whom. In short: DigiLocker issuer and requester partner
onboarding (NeGD, MeitY); NAD registration per institution and NAD / ABC API access (NAD through DigiLocker, UGC); a
Zoom Marketplace app review, a Microsoft Entra multi-tenant app, a Webex integration; Garmin Connect Developer Program
business approval, Google Health API restricted-scope verification for Fitbit, a Polar AccessLink client, Strava API
review; nothing for AISHE, NIRF and NAAC (the institution files through its own login). The hub itself needs none.

## Out of scope (v1.0)

- Moving `OutboundMessaging` and the payment port into `contracts/ports/` (open question 1).
- A vault service as secret backend (open question 3).
- A screen for connections: the org admin dashboard widget comes with the hub build (open question 7).
- Third parties calling Education OS (that is `platform/api-gateway`).
- Bulk data exchange in general (XML, JSON, CSV import and export for users): the old description of this module named
  it; each module owns its own import and export, and `platform/reporting` its exports.

## Open questions (for review)

1. **Existing ports (Himanshu, Gokula Lakshmi).** Move `OutboundMessaging` (messaging-providers) and the payment API
   (payment-sbiepay, its PRD open question 1) into `contracts/ports/` so every port is defined here, each adapter keeping
   its copy? Neither changes shape; it is a follow-up PR per module.
2. **SDK surface (Himanshu, Faizan).** `sdk.integrations.invoke(port, operation, input, idempotency_key, caller_reference)`
   in process, as proposed, or an HTTP call to an internal endpoint? In-process matches how platform services are
   reached today and keeps the invocation off the public API.
3. **Secret store (Faizan, lead).** `file` with an AES-GCM key from the environment for v1.0, as proposed, then OpenBao
   when per-person tokens grow? A vault is new infrastructure on the LXC and needs the lead's approval.
4. **Who may go live (Faizan).** Proposed: `org-admin` holds `integration-hub:connection:go-live`. Should it be the
   super admin instead, at least for DigiLocker and NAD, where Rooman's partner registration is at stake?
5. **Platform or per-organisation apps.** Zoom, Webex and the device providers can be one Rooman app every institution
   authorises (one review, one webhook) or each institution's own app (no Rooman review, more setup). Proposed:
   Rooman's app, with per-organisation credentials allowed as a fallback. Each adapter PRD repeats the trade-off.
6. **Real-time meeting events.** Publish `participant_joined` and `participant_left` as events, or keep them inside the
   hub and publish attendance only once (proposed)?
7. **Org admin screens.** Connections, credentials, health and the delivery log need a page in the Organisation Admin
   dashboard. Which widget, and in which sprint?
8. **Role names.** `org-admin` and `member` are named directly, as in the platform catalogues. Should a module role
   (`integration-hub-admin`) be preferred, held by `org-admin` through its layout?
9. **Event envelope.** Payloads carry `organisation_id`, following the modules on `main`; the event-bus envelope also
   carries it. Same question as grievance's open question 11.
