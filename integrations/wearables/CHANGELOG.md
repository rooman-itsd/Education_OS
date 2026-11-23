# Changelog — wearables

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
### Security
- Default mode changed to `sandbox`; `mock` mode is refused for both environment configuration and per-connection calls unless `EOS_DEV_MODE=true` (Security review 2026-11, N17, #681).
- Verify Garmin push signatures using HMAC-SHA256 (`garmin-webhook-signature` or `x-garmin-signature`) and reject unsigned or improperly signed webhook pushes (Security review 2026-11, N14, #678).
- Encrypt athlete tokens at rest with Fernet (`WEARABLES_DATA_KEY`) and confirm Strava deauthorisations and activity deletions non-destructively with Strava API before deleting athlete records or revoking links (Security review 2026-11, N15, #679).
- A forged Strava event can no longer delete an athlete's data when Strava's token endpoint refuses our own credentials: a deauthorisation is confirmed only when Strava names the athlete's refresh token as invalid, any other refusal, a 5xx or a rate limit confirms nothing and is retried. A real delete is now confirmed after refreshing an expired token. Strava ids must be integers, and a "no" from Strava holds the next confirmation for that athlete back for 30 seconds (follow-up to N15, #679).
- Stored tokens: cleared when a link is revoked; `WEARABLES_DATA_KEY` accepts several comma-separated keys for rotation; the key is checked before a one-time code or refresh token is spent; tokens refreshed by a confirmation are stored at once, and a refused hub refresh retries once with the stored copy.
- Garmin: the signature key must be at least 16 characters; docs now say the signing scheme is not confirmed to be Garmin's and that pushes carry no timestamp (follow-up to N14, #678).

## [0.3.0] - 2026-11-05
Built on the draft contracts (0.2.0); no contract file changed.
- The wearable-data port and the Adapter contract for **Garmin** (OAuth 2.0 + PKCE, push and, on Business Enterprise, pull and
  backfill), **Polar AccessLink** (register with our member id, signed webhook, exercises, daily activity, sleep), **Fitbit**
  through the **Google Health API** (OAuth; endpoints and shapes assumed until access is granted; webhooks refused) and
  **Strava** (OAuth, activities, push subscription without a signature, per-app rate gate).
- Per-athlete linking (`link_account`, minors need a recorded guardian consent), `sync` and `request_backfill`, `read` with a
  stated purpose (logged) and Strava data returned only to its athlete, `link_status`, `unlink_account` deleting every record
  at once, retention (`purge_expired`), and the consumer of `integration-hub.account-link.revoked`.
- `GET /alerts` and the `wearables.alerts` widget for the coach's dashboard (`frontend/`), with `wearables:alert:read` for
  coach and org-admin: statuses and dates only, nothing from Strava beyond "linked".
- Own schema `wearables` (link_state, record, read_log, audit_entry), forced row-level security, Alembic chain `wear_0001`
  with its own version table; audit in the same transaction as every state change.
- Modes `mock` (default), `sandbox`, `live`; live refuses to start without the developer apps of the providers it serves.
- Deviations from the draft: see the build PR (a single `record` table; `link_account` takes the state and PKCE challenge the
  hub owns; `read` takes an optional `requester_person_id`; `sync` for push-only Garmin is a no-op; the widget has no squad
  filter; new keys `MODE`, `PROVIDERS`, `GOOGLE_HEALTH_SCOPES`, `*_AUTHORIZE_URL`, `*_TOKEN_URL`, `SYNC_FAILURE_THRESHOLD`).

## [0.2.0]
- Contracts proposed, no code: PRD for Garmin, Polar, Fitbit (Google Health API) and Strava with sources;
  implements the wearable-data port (copies of the hub's port files in `contracts/ports/`); provider callbacks and the
  coach's device alerts (`GET /alerts`, backing the `wearables.alerts` widget on the coach layout) in
  `contracts/openapi.yaml`; consumes `integration-hub.account-link.revoked` to delete collected data;
  `wearables:alert:read` for coach and org-admin; `config/env.example`.
