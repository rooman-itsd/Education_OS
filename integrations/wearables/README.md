# wearables

Athletes' own device data. Implements the **wearable-data** port defined by `platform/integration-hub`
([`contracts/ports/wearable-data.yaml`](contracts/ports/wearable-data.yaml)) for Garmin, Polar, Fitbit (through the
Google Health API) and Strava: an athlete links their own account, the adapter receives daily summaries, sleep and
workouts as the provider makes them available, normalises them to one shape and fixed units, and lets the sports modules read
them for that athlete. It also backs the coach dashboard's `wearables.alerts` widget.

**Status:** built against the draft contracts (0.3.0). Runs in **mock** mode by default; sandbox and live need each provider's
approval (see "What is mocked until approval"). See [docs/prd.md](docs/prd.md). Heart rate, sleep and body composition are
**health data**: read the "Personal data" section of the PRD before changing anything here.

## Layout

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub (not edited here)
- `contracts/openapi.yaml` — provider callbacks (received by integration-hub) and `GET /alerts`
- `src/eos_wearables/`
  - `application/adapter.py` — the adapter: `describe()` and every operation of the two contracts; `get_adapter()` is the entry point
  - `application/alerts.py` — the coach's alerts; `application/consumers.py` — `integration-hub.account-link.revoked`
  - `infrastructure/providers/` — one client per provider (`garmin`, `polar`, `google_health`, `strava`) and `mock`
  - `infrastructure/http.py` — the only HTTP code; the httpx client is injectable (tests give it a `MockTransport`)
  - `infrastructure/models.py`, `db/` — own tables, Alembic chain with its own version table
  - `api/router.py` — `GET /alerts`
- `frontend/` — the `wearables.alerts` widget (`src/widgets`) and its API client
- `config/env.example` — every key; `docs/data-model.md`, `docs/integration-points.md`
- `tests/` — fixtures under `tests/fixtures/<provider>/`; no test opens a socket

## How the hub uses it

The hub finds the adapter by entry point (`eos.integration_adapters`, name `wearables`), calls the factory, and keeps
`describe()` as the registry row. Every operation is a method `op(ctx, input) -> Result` (`Result(output=...)` or
`Result(error={code, retryable, retry_after_s, detail, provider_code})`). `ctx` is the contract's context; `ctx.account_link`
names the athlete when an operation acts for one person, and `ctx.secrets` holds that athlete's tokens for that call only
(never logged, stored or returned).

- **Linking:** `link_account` (the hub passes the OAuth `state` and PKCE `code_challenge` it owns) returns the provider's
  authorize URL; the hub's callback calls `complete_authorisation`, which activates the link, registers the user where the
  provider needs it (Polar `POST /v3/users`, 409 is success) and asks Garmin for history on the Enterprise tier.
- **Receiving data:** the hub passes each callback's raw request to `verify_inbound(None, request)` (`request["query"]` carries
  `provider`) and, once it has acknowledged it, to `parse_inbound`. Garmin's pushed summaries are stored by `parse_inbound`; every
  other provider's event yields a `data_available` notification and the hub then runs `sync` for that link.
- **Reading:** `read` returns stored records only (it never calls a provider), for a stated `purpose`, which is logged.
- **Unlinking:** `unlink_account` (and the `integration-hub.account-link.revoked` consumer, and a provider's own
  deregistration) delete every record collected under the link at once. `purge_expired` is the daily retention job.

## Strava and who may see it

Strava's API agreement allows its data to be shown only to the athlete it belongs to. Strava records are stored `athlete_only`,
`read` returns them for the purpose `athlete_self` (with the requester equal to the athlete) and for nobody else, unless the
connection's `strava_shared_display_approved` is set after Strava approves wider display in writing and the athlete consented
(it is checked again at every read, so withdrawing it hides the data at once). The alerts show Strava links only as "linked":
no recency, no sync time. Strava sends **no signature**: an event is accepted only for our `subscription_id` and an athlete with
an active link, and nothing in the body is trusted, the data is fetched afterwards with the athlete's own token.

## Garmin

Business Starter is push only; Enterprise pulls and can backfill (connection setting `garmin_tier`). Garmin documents its
notification signing inside the program, so until Rooman is approved a push is trusted only as far as its user id matching an
active link, and a forged push for a known athlete id could write records for them. Do not point a production Garmin
endpoint at this adapter before the program's signing is added to `GarminProvider.verify_inbound`.

## Fitbit (Google Health API)

Everything specific to the Google Health API is an assumption until access is granted (the PRD's "Not verified"): the API
base URL and scopes have no default and are required, the resource paths and response shapes are the table in
`infrastructure/providers/google_health.py`, and its webhooks are refused (data arrives by the daily `sync`).

## Configuration

Every key is in [config/env.example](config/env.example), prefixed `WEARABLES_`. `MODE` is `mock` (default), `sandbox` or
`live`; the hub's per-call `ctx.mode` wins. **Live refuses to start** (`get_adapter()` raises `not_configured`) without the
developer app credentials of every provider in `PROVIDERS` (default all four). A connection's settings (in the hub):
`data_types`, `share_with_coaches`, `strava_shared_display_approved`, `garmin_tier`.

## Getting sandbox access

| Provider | How |
|---|---|
| Polar | Create a client at https://admin.polaraccesslink.com (self-service), set the redirect URI, create the webhook (the signature key is returned once: `WEARABLES_POLAR_WEBHOOK_SIGNATURE_KEY`) |
| Strava | Register an app at https://www.strava.com/settings/api; create the push subscription with our `verify_token` (`WEARABLES_STRAVA_VERIFY_TOKEN`) and put its id in `WEARABLES_STRAVA_SUBSCRIPTION_ID`; one athlete (a staff account) until Strava's review |
| Garmin | Apply to the Garmin Connect Developer Program (Business tier); until approved, fixtures only |
| Fitbit | Google Health API access and restricted-scope verification; test users before that |

## What is mocked until approval

| What | Until |
|---|---|
| All four providers' API calls in `mock` mode (an in-process stand-in; verification, parsing and the authorisation URLs are real) | accounts: Polar and Strava can be had now; Garmin and Google need approval |
| The fixtures are the providers' documented example payloads, not recordings (`tests/fixtures/README.md`) | the first sandbox run replaces them |
| Fitbit's endpoints and shapes, and Fitbit webhooks | Google grants access and documents webhook verification |
| Garmin's signed notifications, tiers and fees | the Garmin program approves Rooman |
| The widget's athlete names and squad filter | the shell can pass a squad and a name lookup (see below) |

## The widget `wearables.alerts`

`platform/identity/config/dashboards/coach.yaml` already lists `wearables.alerts`; `frontend/src/widgets` exports it behind
`wearables:alert:read` (granted to coach and org-admin in `contracts/permissions.yaml`) and it reads `GET /alerts`. Statuses and
dates only. It shows an athlete as "Athlete …abc123" because the adapter knows ids, not names, and a widget may not import
another module; it passes no squad filter for the same reason (the API takes `person_id`, up to 200, for the day the shell can
pass one). **Host wiring that is outside this module and not done here:** listing `wearables` in
`apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`, removing `wearables.alerts` from
`NOT_BUILT` in `tests/e2e/dashboards/coach.spec.ts`, and `docs/team/sprint-v1.0.md`.

## Tests

```bash
PYTHONPATH=src:../../packages/core/src:../../packages/testing/src python -m pytest tests
(cd frontend && pnpm test && pnpm typecheck)
```
