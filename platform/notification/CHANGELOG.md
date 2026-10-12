# Changelog — notification

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- `contracts/openapi.yaml`: send a message, delivery history and status, resend a failure,
  templates with preview, recipient preferences, and the in-app inbox.
- Sends are idempotent on `client_token`, because event delivery is at-least-once and the same
  event may arrive twice.
- `contracts/events.yaml`: publishes `notification.message.sent|failed|bounced` and
  `notification.preferences.changed`; consumes the nine `tenancy.*`, `billing.*` and
  `identity.*` events that are already published by code in this repo.
- `contracts/permissions.yaml`: message send/read/resend, template read/write, preference
  management, and super-admin `platform:notification:read`.
- `docs/prd.md`: the boundary against messaging-providers, scheduler, audit and event-bus; the
  transactional-mail rule that cannot be opted out of; and the two constraints on replacing
  `eos_core.notify` — `eos_testing` reads it, and the live call sends before it commits.
- `config/env.example`: `memory` transport is the default, preserving today's test behaviour.
- Module scaffolded.
