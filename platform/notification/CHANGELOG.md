# Changelog — notification

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Activation (#79 follow-up). Enabled in `apps/backend/config/modules.enabled.yaml`, so the host installs,
  mounts and migrates this module.
- Permissions per the contract owner's scheme: catalogue blocks named with platform role ids (`member`,
  `org-admin`, `super-admin`, `service`) in place of the module-named `notification-admin` and
  `notification-viewer`, which no profile assigned and so granted nothing. New keys `notification:self:read`
  and `notification:self:manage` guard the inbox and own-preference routes and are granted to `member`;
  another user's preferences still need `notification:preference:manage`. `notification:message:send` is held
  only by `service`.
- `messages.accept_in_transaction()` and `messages.deliver_accepted()`: the in-process path for a caller that
  owns its transaction (tenancy). The row commits with the caller's work; nothing is committed, rolled back or
  sent by notification on the caller's behalf. `deliver_accepted` dispatches in a session of its own, so called
  before the caller's commit, or after a rollback, it finds no message (404) and sends nothing. Acceptance is not
  delivery: the returned message's status says what happened. `send_message` uses the same accept and dispatch.
  On SQLite the caller's transaction is begun explicitly before the insert's savepoint: the driver otherwise
  opened none before a first write, so the savepoint was the outermost transaction and releasing it committed the
  message, which then survived the caller's rollback.
- The memory transport keeps what it "sends" in its own `transport.sent` list instead of `eos_core.notify.sent`,
  so the legacy stub can be deleted once tenancy and `eos_testing` stop using it.
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
