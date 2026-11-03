# Changelog — event-bus

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Delivery is per consuming module (#316 follow-up; #83's "consumer groups per module"). Chain 0003 adds
  `event_bus_delivery`, one row per (event, module) with `organisation_id` and row-level security. A module's
  delivered mark commits with its handler; a module already delivered is skipped; a failing module no longer
  stops the modules after it. A retry, and an operator's replay, re-run only the failed modules. The dead-letter
  notice carries `failed_modules`; `GET /events/{id}` and replay show `deliveries`. Contract 0.2.0 (additive).
- The claim is `FOR NO KEY UPDATE SKIP LOCKED`, so a consumer's delivery row (a foreign key to the event) is not
  blocked by the relay's own lock.
- `EVENT_BUS_MAX_ATTEMPTS` defaults to 20 (about an hour at the 300 s cap) instead of 8, which dead-lettered an
  event after about two minutes of failures.
- The relay (#316, was #83): drains `outbox_event` oldest first, `FOR UPDATE SKIP LOCKED` on Postgres; marks
  delivered events published; retries a failure with exponential backoff and dead-letters it after
  `EVENT_BUS_MAX_ATTEMPTS`, raising `event-bus.event.dead-lettered` (never for the bus's own events); raises
  `event-bus.relay.stalled` once per stall; prunes delivered events after `EVENT_BUS_RETENTION_DAYS`. Runs as
  `python -m eos_event_bus`. New setting `EVENT_BUS_RETRY_CAP_S`.
- In-process transport: consumers advertise themselves on the `eos.event_consumers` entry-point group. Each runs
  in its own transaction, in the event's organisation with the row-level-security bypass off; delivery runs
  outside the claim's platform scope, and refuses to run an organisation's consumer inside one.
- Alembic chain `event_bus_0001`/`0002` owns `outbox_event`: 0001 creates it as `eos_core` did (recorded only
  where it exists), 0002 adds `version`, `attempts`, `last_error`, `published_at`, `next_attempt_at` and the
  `(published, occurred_at)` index, and marks rows written before the relay existed as published.
- Operator API from `contracts/openapi.yaml`: list, get, replay a dead-lettered event (409 otherwise), relay health.
- `contracts/permissions.yaml`: blocks named with platform role ids. `org-admin` reads and replays its own
  organisation's events; `super-admin` also reads relay health and every organisation's events. The
  `event-bus-operator` and `event-bus-viewer` blocks, which no profile assigns, are removed.
- Enabled in the host (`apps/backend/config/modules.enabled.yaml`).
- Event envelope defined in `contracts/events.yaml`: id, name, version, organisation_id,
  actor, occurred_at, payload. Every module's events inherit it.
- Delivery semantics stated: at-least-once, no ordering guarantee, consumers idempotent on
  envelope id, no cross-organisation delivery.
- Outbox relay design in `docs/outbox-relay.md`, broker-agnostic behind a transport port so
  the pending broker decision blocks no one. Requests four columns and an index on
  `eos_core.OutboxEvent` (architecture lead's change).
- Operator API in `contracts/openapi.yaml`: list and inspect events, replay a dead-lettered
  event, relay health.
- Permissions: `event-bus:event:read|replay`, `event-bus:relay:read`,
  `platform:event-bus:admin`.
- `docs/prd.md` with the scope boundary against audit, scheduler and integration-hub.
- Module scaffolded.
