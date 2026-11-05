# video-conferencing

Zoom, Microsoft Teams, Webex and self-hosted Jitsi adapter for online classes, interviews and meetings. Implements the
**meetings** port defined by `platform/integration-hub` ([`contracts/ports/meetings.yaml`](contracts/ports/meetings.yaml)):
create, change and cancel a meeting, give each participant the right join link, and report started, ended, attendance
and recordings, the same way whichever provider an institution uses.

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — provider callbacks (received by integration-hub) and a read-only meetings view
- `src/` — one provider client per vendor behind the port
- `config/env.example` — Rooman's platform apps for Zoom, Microsoft and Webex
- `tests/` — contract tests against recorded fixtures, a local Jitsi, and each vendor's developer account when configured
