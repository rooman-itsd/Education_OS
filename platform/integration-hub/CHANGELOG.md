# Changelog — integration-hub

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Backend built on the draft contracts (0.2.0): connections per organisation with settings validated against the
  provider's schema; write-only credentials in a secret store (`file`: AES-256-GCM, one 0600 file per secret, key
  rotation; `env`: read only, development), never in the database; mock, sandbox and live with the separate go-live
  key; OAuth with PKCE S256 for organisations and for people's account links, single-use hashed state, allowed return
  hosts; `/inbound` intake (raw body kept, adapter's `verify_inbound` decides, handshakes, dedup, acknowledge first,
  processing after the response and in the sweep); provider requests answered synchronously; health on demand
  (rate limited) and scheduled; delivery log with attempts, retries with exponential backoff and full jitter,
  per-connection throttling, dead letters and manual retry; retention; super admin overview; audit through
  platform/audit and events through the outbox in the same transaction; port events normalised from outputs and
  callbacks. Alembic chain `integration_hub_0001` (7 tables, forced RLS).
- Adapters found on `eos.integration_adapters`; the calling convention is in the README. Modules call ports through
  the `eos.integration_hub` / `invoke` entry point (packages/sdk has no clients yet).
- `contracts/events.yaml`: `integration-hub.job.finished` added (platform/scheduler's protocol for the four jobs).
- Enabled in `apps/backend/config/modules.enabled.yaml`.
- Contracts proposed (0.2.0), no code: PRD; six ports in `contracts/ports/` (certificate-issuance, academic-records,
  regulatory-submission, meetings, wearable-data, inter-institution-records) and the Adapter contract every adapter
  implements, with one error vocabulary; the hub API (connections, write-only credentials kept in a secret store,
  mock/sandbox/live modes and going live, OAuth for organisations and people, provider callbacks with verification,
  health, delivery log and retries, super-admin overview); 25 events (connections, account links, deliveries, and
  port events normalised across providers); 10 permission keys for `org-admin`, `member` and `super-admin`.
  `module.yaml`: status in-progress, owner, dependencies on event-bus, scheduler, documents and notification.
- Module scaffolded.
