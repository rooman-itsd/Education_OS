# Changelog — video-conferencing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]

## [0.3.0] - 2026-11-05
Built on the draft contracts (0.2.0); no contract file changed.
- The meetings port and the Adapter contract for **Zoom** (account-level OAuth app or an institution's own Server-to-Server
  app; per-host daily create/update limit with an optional host pool), **Microsoft Teams** (Graph onlineMeetings, application
  permissions, access-policy error with the PowerShell hint, recordings subscription kept alive), **Webex** and **Jitsi**
  (random room names, per-person HS256 JWT join links).
- Webhooks: Zoom `x-zm-signature` and the `endpoint.url_validation` handshake, Graph `validationToken` and per-subscription
  `clientState` (derived from a stored nonce, never stored), Webex `X-Webex-Signature` / `X-Spark-Signature`.
- Own schema `video_conferencing` (meeting, attendance, recording, graph_subscription, host_quota, audit_entry), forced
  row-level security, Alembic chain `vc_0001` with its own version table. Join links and passcodes encrypted (Fernet).
- `GET /meetings` operator view with `video-conferencing:meeting:read`.
- Modes `mock` (default), `sandbox`, `live`; live refuses to start without its credentials.
- Deviations from the draft: `create_meeting` and `update_meeting` take an optional hub `meeting_id`; `fetch_attendance`
  takes an optional `roster` ([{person_id, email}]) because the adapter has no directory of people; `attendance_ready`
  carries `not_before`; Zoom `participant_joined/_left` are acknowledged but publish nothing (no person id to give);
  `verify_inbound` output adds `ack_status` (Graph wants 202); `due_attendance` and `renew_subscriptions` are added as
  scheduler jobs; new keys `MODE`, `DATA_KEY`, `PROVIDERS`, `PUBLIC_BASE_URL`, `ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY`,
  `MAX_RECORDING_BYTES`.

## [0.2.0]
- Contracts proposed, no code: PRD for Zoom, Microsoft Teams (Graph), Webex and self-hosted Jitsi with sources;
  implements the meetings port (copies of the hub's port files in `contracts/ports/`); webhook verification for each
  provider and a read-only meetings view in `contracts/openapi.yaml`; no events of its own;
  `video-conferencing:meeting:read` for org-admin; `config/env.example`.
