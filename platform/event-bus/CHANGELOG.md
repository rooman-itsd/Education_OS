# Changelog — event-bus

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
