# video-conferencing

Zoom, Microsoft Teams, Webex and self-hosted Jitsi adapter for online classes, interviews and meetings. Implements the
**meetings** port defined by `platform/integration-hub` ([`contracts/ports/meetings.yaml`](contracts/ports/meetings.yaml)):
create, change and cancel a meeting, give each participant the right join link, and report started, ended, attendance
and recordings, the same way whichever provider an institution uses.

**Status:** built against the draft contracts (0.3.0). Runs in **mock** mode by default; sandbox and live need each
provider's approval (see "What is mocked until approval"). See [docs/prd.md](docs/prd.md).

## Layout

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub (not edited here)
- `contracts/openapi.yaml` — provider callbacks (received by integration-hub) and a read-only meetings view
- `src/eos_video_conferencing/`
  - `application/adapter.py` — the adapter: `describe()` and every operation of the two contracts; `get_adapter()` is the entry point
  - `infrastructure/providers/` — one client per vendor (`zoom`, `teams`, `webex`, `jitsi`) and `mock`
  - `infrastructure/http.py` — the only HTTP code; the httpx client is injectable (tests give it a `MockTransport`)
  - `infrastructure/models.py`, `db/` — own tables, Alembic chain with its own version table
  - `api/router.py` — `GET /meetings` (operator view)
- `config/env.example` — every key; `docs/data-model.md`, `docs/integration-points.md`
- `tests/` — fixtures under `tests/fixtures/<provider>/`; no test opens a socket

## How the hub uses it

The hub finds the adapter by entry point (`eos.integration_adapters`, name `video-conferencing`), calls the factory, and
keeps `describe()` as the registry row. Every operation is a method `op(ctx, input) -> Result`:

```python
adapter = get_adapter()
adapter.create_meeting(
    ctx,
    {
        "meeting_key": "<class session id>",
        "title": ...,
        "starts_at": ...,
        "duration_minutes": 45,
        "timezone": "Asia/Kolkata",
        "host": {"email": ...},
        "options": {...},
    },
)
# Result(output={...} | error={code, retryable, retry_after_s, detail, provider_code}, provider_reference=...)
```

`ctx` is the contract's context (`organisation_id`, `connection_id`, `provider`, `mode`, `settings`, `secrets`, ...). Secrets
are used for that call only; they are never logged, stored or returned. Inbound callbacks: the hub passes the raw request to
`verify_inbound(ctx, request)` (verdict `accept`, `reject` or `handshake`) and, after acknowledging, to
`parse_inbound(ctx, request)`, which returns the port's notifications. Jobs for the hub's scheduler: `due_attendance` (Teams
has no "ended" event: list meetings whose report should now exist) and `renew_subscriptions` (Graph subscriptions last under
3 days).

## Configuration

Every key is in [config/env.example](config/env.example), prefixed `VIDEO_CONFERENCING_`. The ones that decide behaviour:

| Key | Meaning |
|---|---|
| `MODE` | `mock` (default), `sandbox` or `live`. The hub's per-call `ctx.mode` wins. Live refuses to start (`get_adapter()` raises `not_configured`) without the data key, the public URL and the platform apps of every provider in `PROVIDERS` |
| `DATA_KEY` | Fernet key protecting stored join links and passcodes; required outside mock |
| `ZOOM_*`, `TEAMS_*`, `WEBEX_*` | Rooman's platform apps (one per provider and deployment) |
| `ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY` | Zoom's 100 create/update calls per host per day; the adapter holds the 101st (`throttled`, `retry_after_s` to 00:00 UTC) or moves to the connection's host pool |
| `WEBHOOK_TOLERANCE_S`, `ATTENDANCE_DELAY_MIN`, `JITSI_TOKEN_TTL_S` | as the PRD describes |

An institution's own credentials, tenant id, Jitsi app id and secret are entered on its integration-hub connection and reach
the adapter in `ctx.settings` / `ctx.secrets`.

## Getting sandbox access

| Provider | How |
|---|---|
| Zoom | A Zoom developer account at https://marketplace.zoom.us: create a general OAuth app (or a Server-to-Server app for one account), add the meeting, report and recording scopes and an event subscription whose URL is the hub's `/inbound/video-conferencing`; put its secret token in `ZOOM_WEBHOOK_SECRET_TOKEN` |
| Microsoft Teams | A Microsoft 365 tenant Rooman controls (the free developer sandbox is restricted: a trial or a Visual Studio subscription), a multi-tenant Entra app with application permissions `OnlineMeetings.ReadWrite.All`, `OnlineMeetingArtifact.Read.All`, `OnlineMeetingRecording.Read.All`, admin consent, and the application access policy (`New-CsApplicationAccessPolicy`, `Grant-CsApplicationAccessPolicy`, up to 30 minutes to apply) |
| Webex | https://developer.webex.com: an integration with the meeting scopes `begin_authorisation` asks for, authorised by an org admin who is also a site admin |
| Jitsi | None: `docker-jitsi-meet` with `ENABLE_AUTH=1 AUTH_TYPE=jwt JWT_APP_ID=... JWT_APP_SECRET=...` locally; `tests/test_live_jitsi.py` runs against it when `VIDEO_CONFERENCING_TEST_JITSI_URL` and `..._SECRET` are set |

## What is mocked until approval

| What | Until |
|---|---|
| Zoom, Teams and Webex API calls in `mock` mode (a stand-in makes up ids and links; verification, parsing and Jitsi are real) | an account for each: Zoom developer account and, for other institutions, Zoom's app review; a Microsoft 365 tenant and Rooman's Entra app; a Webex developer integration |
| The test fixtures are the providers' documented example payloads, not recordings from a live account | the first sandbox run replaces them (see `tests/fixtures/README.md`) |
| `import_recording` into `platform/documents` | `packages/sdk` ships a documents client: the adapter takes a `DocumentSink` (tests use a fake) and answers `not_configured` without one |
| Webex endpoint details and event names, Zoom `meeting.*` event names, where Teams recordings land | confirmed against each provider when the adapter first meets it (docs/prd.md, "Not verified") |

## Deviations from the draft contract

Listed in the build PR and in [CHANGELOG.md](CHANGELOG.md); none changes the port.

## Tests

```bash
PYTHONPATH=src:../../packages/core/src:../../packages/testing/src python -m pytest tests
```
