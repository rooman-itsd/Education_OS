# video-conferencing: integration points

| With | How |
|---|---|
| `platform/integration-hub` | Finds the adapter by entry point `eos.integration_adapters` / `video-conferencing`; passes the call context; receives provider callbacks at `/inbound/video-conferencing` (app-level Zoom) and `/inbound/video-conferencing/{connection_key}` and asks `verify_inbound` / `parse_inbound`; keeps connections, OAuth tokens and secrets; publishes the port's events. Not imported: the port files in `contracts/ports/` are copies |
| `platform/documents` | `import_recording` streams a recording into a `DocumentSink` (to be backed by `packages/sdk`); only when the caller asks |
| `platform/identity` | Registers `video-conferencing:meeting:read` (org-admin); `GET /meetings` reads the platform token through `eos_core` |
| `platform/audit` | Until the audit SDK ships, `video_conferencing_audit_entry` in the same transaction |
| Callers (lms, timetable-attendance, selection-process, alumni) | Through the meetings port via `packages/sdk`, never this API |

## Providers

| Provider | Endpoints used | Callbacks | Credentials |
|---|---|---|---|
| Zoom | `POST /users/{id}/meetings`, `PATCH`/`DELETE /meetings/{id}`, `GET /past_meetings/{uuid}/participants`, `GET /meetings/{id}/recordings`, `GET /users/me`, OAuth token/revoke | `meeting.started/ended/deleted`, `recording.completed`; `endpoint.url_validation` | Marketplace app (platform) or an institution's S2S app (connection secrets) |
| Teams | `POST /users/{id}/onlineMeetings`, `PATCH`/`DELETE`, `.../attendanceReports`, `.../recordings`, `.../transcripts`, `POST`/`PATCH /subscriptions`, client-credentials token | Graph change and lifecycle notifications | Rooman's Entra app (platform), tenant id (connection) |
| Webex | `POST /meetings`, `GET`/`PUT`/`DELETE /meetings/{id}`, `/meetingParticipants`, `/recordings`, `/webhooks`, OAuth | webhooks `meetings` (started, ended, deleted), `recordings` (created) | Rooman's integration (platform), tokens and `webhook_secret` (connection) |
| Jitsi | none (JWT minted locally); `GET {base_url}/` for the healthcheck | none | `app_id` (setting), `app_secret` (connection secret) |
