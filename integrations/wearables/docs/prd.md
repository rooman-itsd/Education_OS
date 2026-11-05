# wearables: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #145 · Depends on the integration-hub contracts (the wearable-data port).

## Purpose

Sports colleges train athletes who already wear a Garmin, Polar or Fitbit watch or record on Strava. Coaches want that
training load, sleep and recovery next to the fitness tests and results they keep in athlete-performance, without
athletes exporting files. This adapter lets an athlete connect their own device account, receives the data as the
provider makes it available, normalises it to one shape and fixed units, and lets the sports modules read it for that
athlete.

It implements the **wearable-data** port ([contracts/ports/wearable-data.yaml](../contracts/ports/wearable-data.yaml))
and the Adapter contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by
`platform/integration-hub`. Callers: `modules/sports/athlete-performance` and `modules/sports/sports-nutrition-health`.
It also backs the `wearables.alerts` widget already on the coach's dashboard layout
(`platform/identity/config/dashboards/coach.yaml`).

## What it is not

| Not this | That belongs to |
|---|---|
| Training plans, readiness scores, thresholds and their alerts ("load too high") | athlete-performance (open question 2) |
| Nutrition and medical decisions | sports-nutrition-health |
| Linking and unlinking, tokens, OAuth state | `platform/integration-hub` (account links, `integration-hub:self:link`) |
| A mobile app reading on-device stores (Health Connect, Apple HealthKit) | not in v1.0 (open question 3) |

## Providers (sources)

| Provider | Access and approval | Auth | Data | Delivery | Rate limits | Source |
|---|---|---|---|---|---|---|
| **Garmin** Connect Developer Program (Health, Activity APIs) | Apply. **Business Starter**: approved app, push only, no history, limited users. **Business Enterprise**: push or ping/pull, a month or more of history, unlimited users, "tailored commercial terms". Personal tier: own data only | OAuth 2.0 with PKCE (S256); the athlete picks data permissions on Garmin's consent screen; OAuth 1.0a is legacy | dailies, epochs, sleeps, stress details, HRV, body composition, activities, respiration, pulse ox | Push (data) or ping (then pull); `deregistrations` and `userPermissionsChange` notifications; backfill by request where the tier allows | not published | https://developer.garmin.com/gc-developer-program/overview/; OAuth 2.0 PKCE spec https://developerportal.garmin.com/sites/default/files/OAuth2PKCE.pdf (endpoints from its links) |
| **Polar** AccessLink API v3 | Self-service client at admin.polaraccesslink.com; no partner approval visible | OAuth 2.0 code; authorise at flow.polar.com, token at polarremote.com with Basic auth; tokens do not expire; then `POST /v3/users` with our member id (409 if registered); `DELETE /v3/users/{id}` deregisters | exercises, daily activity, sleep, physical info | One webhook per client; `signature_secret_key` returned once; HMAC-SHA256 in `Polar-Webhook-Signature`; a PING on creation; deactivated after 7 days of failures | 15 min: 500 + 20 per user; 24 h: 5,000 + 100 per user | https://www.polar.com/accesslink-api/ |
| **Fitbit** (through the **Google Health API**) | The legacy Fitbit Web API is shut down (Google gives 2 Nov 2026; Fitbit's pages say 30 Oct 2026) and users must re-consent. All Google Health API scopes are **restricted**: a privacy and security review is required | Google OAuth 2.0 | Consolidated data-type bundles; Health Connect parity planned to Q1 2027 | Webhooks ("auto-subscriptions"), telemetry planned Q4 2026 | not published | https://developers.google.com/health/about; legacy reference https://dev.fitbit.com/build/reference/web-api/developer-guide/using-subscriptions/ |
| **Strava** API v3 | Register an app. Default capacity is small; beyond 10 athletes needs Strava's review. **API Agreement: data may be shown only to the athlete it belongs to**; sharing with others needs explicit consent; Strava may charge; on termination delete all Strava data and certify it | OAuth 2.0, scope `activity:read_all` | activities (no daily summaries, no sleep) | One push subscription per app; GET handshake with `hub.challenge` answered within 2 s; events carry ids only (`object_type`, `object_id`, `aspect_type`, `owner_id`), **no signature**; respond within 2 s, up to 3 attempts; deauthorisation arrives as an athlete `update` with `authorized: false` | 200 per 15 min and 2,000 per day per app (non-upload 100 and 1,000) | https://developers.strava.com/docs/webhooks/, https://developers.strava.com/docs/rate-limits/, https://developers.strava.com/guidelines/, https://www.strava.com/legal/api |
| Health Connect (Android), Apple HealthKit | On-device APIs only; no cloud API. Need a mobile app that reads and uploads | — | — | — | — | https://developer.android.com/health-and-fitness/health-connect |

**Not verified**: Garmin's own documentation of notifications, backfill and any webhook signing (available inside the
program after approval), Garmin's fees, Google Health API endpoints, quotas, sandbox and webhook verification, Polar's
current non-transactional endpoints, and whether Strava's newer terms add AI or analytics restrictions. Each is
confirmed when access is granted; the port does not depend on them.

## Design

### Linking (person scope)

1. The organisation's admin enables a provider for the organisation (an integration-hub connection, port
   wearable-data). There are no organisation secrets: all four providers use Rooman's developer apps
   (`config/env.example`); the connection holds settings only: which data types are collected and whether coaches see
   them.
2. The athlete opens "Connect a device" (a screen in athlete-performance) which calls the port's `link_account`; our
   page shows what will be collected and who will see it, then redirects to the provider. Nobody can link an account
   for someone else.
3. The hub's OAuth callback stores the tokens in the secret store; the adapter registers the user where the provider
   requires it (Polar `POST /v3/users`) and requests a backfill of `WEARABLES_DEFAULT_BACKFILL_DAYS` where allowed.
   The hub publishes `integration-hub.account-link.connected`.

### Receiving data

All four providers deliver to one app-level URL each: `/inbound/wearables?provider=<provider>` on the hub.

| Provider | Verification | Then |
|---|---|---|
| Polar | HMAC-SHA256 of the raw body with the signature key | Fetch the new exercise, activity or sleep with the user's token |
| Strava | No signature exists. Accept only our `subscription_id` and an `owner_id` with an active link; trust nothing else in the body | Fetch the activity with the athlete's token; `authorized: false` revokes the link |
| Garmin | Match each entry to an active link by Garmin user id and token; signing as Garmin documents it | Store pushed summaries, or pull for pings; deregistration revokes the link; permission change narrows it |
| Google Health | As Google documents | Fetch the changed data types |

Every request is acknowledged before processing (Strava gives 2 seconds). Each record is normalised to the port's
`records` shapes (metres, seconds, kilograms, bpm, kcal) and upserted on `(account_link_id, provider_record_id)`, so
a redelivery or a correction changes one row. The hub publishes `integration-hub.wearable-data.received` with ids and
dates only.

A scheduled `sync` per link (daily) catches anything a missed webhook dropped, within rate limits.

### Reading data

`read(person_id, data_type, from, to, purpose)` returns stored records only; it never calls a provider. The calling
module states its purpose, recorded with the read. **Strava records are returned only when the purpose is the
athlete's own view** (`athlete_self`), because Strava's agreement forbids showing one athlete's data to anyone else;
they are returned for coach purposes only if the connection's `strava_shared_display_approved` is set after Strava
approves it and the athlete consented (open question 4). `capabilities.display_to_others_allowed` is false for Strava.

### Coach alerts (widget `wearables.alerts`)

`GET /alerts` lists athletes whose link expired or was revoked, whose sync keeps failing, or who sent no data for
`WEARABLES_STALE_AFTER_DAYS`. The widget passes the coach's squad (person ids from athlete-performance) as a filter.
Statuses and dates only, never readings, so it is safe for any coach and shows nothing from Strava beyond "linked".

### Unlinking and erasure

The athlete disconnects (`DELETE /me/account-links/{id}` on the hub), an admin revokes the link, or the provider
reports deregistration. The hub revokes at the provider (Polar `DELETE /v3/users/{id}`, Strava deauthorize, Garmin
deregistration) and publishes `integration-hub.account-link.revoked`; this adapter consumes it and **deletes every
record collected under the link** at once. Records older than `WEARABLES_RETENTION_DAYS` are deleted daily.

### Connection (per organisation, in integration-hub)

| Kind | Name | Notes |
|---|---|---|
| setting | `data_types` | Which of daily_summary, activity, sleep, hrv, body_composition are collected |
| setting | `share_with_coaches` | Whether coach-purpose reads return data at all (default true, except Strava) |
| setting | `strava_shared_display_approved` | Only after Strava's written approval and the athlete's consent |
| secret | none per organisation | Rooman's apps are platform credentials; athletes' tokens are per link |

### Error mapping

| Provider answer | Port error | Retryable |
|---|---|---|
| Network error, timeout | `transport_unavailable` | yes |
| 5xx | `provider_error` | yes |
| 429 (Strava resets at :00, :15, :30, :45 and midnight UTC) | `throttled` | yes |
| 401, token revoked, refresh refused | `consent_required`; the link becomes `expired` | no |
| 403 for a data type the athlete did not grant | `consent_required` for that type | no |
| Polar 409 on register | treated as success | — |
| Data type not offered by the provider (sleep on Strava) | `unsupported` | no |

### Rate limits

Strava's per-app limit is the tightest: 100 non-upload requests per 15 minutes is a fetch per event for about 100
athletes training at once. The adapter queues fetches per provider, honours the 15-minute windows, and asks Strava for
a higher limit before more than a squad links (External dependencies). Polar's limits grow with users. Garmin pushes
data, so it costs no calls.

## Sandbox and mock

| Provider | How it is tested in v1.0 |
|---|---|
| Polar | A real Polar account and Rooman's self-service client; recorded fixtures in CI |
| Strava | Rooman's app in its default single-athlete capacity with a staff account; recorded fixtures in CI |
| Garmin | Recorded fixtures until the program approves Rooman; then the Starter tier |
| Google Health (Fitbit) | Recorded fixtures until Google grants access and verification; test users before that |

Fixtures include signed and unsigned webhooks, wrong signatures, Strava's handshake, deauthorisation and
deregistration, a token refresh failure and 429s. Live per provider when its approval arrives (lead's decision,
5 Nov 2026).

## Data model (summary)

Own schema `wearables`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| daily_summary, activity, sleep, hrv, body_composition | id, organisation_id, account_link_id, person_id, provider, provider_record_id, the port's normalised fields, display_scope (all, athlete_only), received_at |
| link_state | organisation_id, account_link_id, person_id, provider, last_synced_at, consecutive_failures, last_error_code |
| read_log | organisation_id, person_id, caller_module, purpose, data_type, from, to, read_at |

## Personal data (DPDP Act 2023)

Heart rate, sleep and body composition are **health data**: the most sensitive personal data Education OS holds.

- **Consent** is the athlete's own, given at the provider and on our page with the purpose shown, and withdrawable at
  any time by disconnecting. An institution cannot link a device for an athlete, and a coach cannot require it through
  this system.
- **Minors.** Some sports-college athletes are under 18; under the DPDP Act a child's data needs verifiable parental
  consent. Linking is refused for an athlete marked as a minor until a guardian's consent is recorded (open question 5).
- **Purpose and minimum data.** Only the data types the organisation enabled are fetched; reads are logged with a
  purpose; events carry no readings.
- **Erasure.** Disconnecting deletes the records at once; retention deletes old records; provider-side copies are the
  provider's under its own terms with the athlete.
- **Where data goes.** The providers hold the athlete's data under their own agreement with the athlete (Garmin, Polar,
  Google, Strava; mostly outside India). Education OS keeps its normalised copy on its own servers in India.

## Permissions and events

- `wearables:alert:read` (coach, org-admin): `GET /alerts`.
- Athletes use `integration-hub:self:link`; reading data goes through the port under the calling module's permissions.
- No events of its own: the hub publishes `integration-hub.wearable-data.received` and the account-link events. The
  adapter consumes `integration-hub.account-link.revoked`.

## External dependencies (what Rooman must apply for)

| What | With whom | How | Needed for |
|---|---|---|---|
| **Garmin Connect Developer Program**, Business tier (Starter to begin, Enterprise for history and pull); commercial terms | Garmin | https://developer.garmin.com/gc-developer-program/overview/ (apply through the developer portal) | Garmin |
| **Google Health API** access and **restricted-scope verification** (privacy and security review) for Rooman's Google OAuth app | Google | https://developers.google.com/health/about | Fitbit devices |
| Polar AccessLink client | Polar | https://admin.polaraccesslink.com (self-service) | Polar |
| **Strava app review** for more than the default athletes and a rate-limit increase (developer program form, screenshots, brand compliance); written approval before any coach sees Strava data | Strava | https://www.strava.com/settings/api, https://developers.strava.com/docs/rate-limits/ | Strava beyond one squad |
| A privacy notice covering device data, and legal review of the Strava and Garmin terms | Rooman legal (DPDP pass) | — | Going live |

## Out of scope (v1.0)

- Health Connect and Apple HealthKit (need a mobile app; open question 3), WHOOP, Oura, Coros, Suunto.
- Intraday second-by-second data, GPS tracks and routes.
- Writing to a provider (workouts pushed to a watch).

## Open questions (for review)

1. **Provider order (Himanshu).** Polar and Strava can be built and tested now; Garmin and Google need approvals with
   unknown lead times. Build all four against fixtures (proposed), or drop Google until verified?
2. **Thresholds and readiness (athlete-performance owner).** Should "load too high" style alerts live in
   athlete-performance (proposed), leaving `wearables.alerts` to device and link problems?
3. **Mobile app.** Health Connect and HealthKit need a mobile app. Is one planned after v1.0?
4. **Strava and coaches.** Proposed: Strava data is visible to the athlete only until Strava approves wider display in
   writing. Agreed?
5. **Minors.** Where does guardian consent get recorded (student-information?), so linking can check it?
