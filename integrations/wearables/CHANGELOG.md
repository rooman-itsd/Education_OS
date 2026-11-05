# Changelog — wearables

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]

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
