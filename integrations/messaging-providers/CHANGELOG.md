# Changelog — messaging-providers

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- The outbound email send path. `SmtpEmailProvider` implements the OutboundMessaging port's `send`,
  `capabilities` and `healthcheck` over the standard library's `smtplib` (no third-party mail library), configured from
  `MESSAGING_PROVIDERS_SMTP_*` and defaulting to a local MailHog. Every provider failure maps to one of the four
  port reason codes; provider text never leaves the module, and no body, address, subject or credential is
  logged. `reply_to` is supported and advertised through `capabilities().supports_reply_to`. Attachments are
  refused, not dropped. `retry_after_s` is always null: SMTP has no retry-after signal. A line break in any
  header is refused for good (`invalid_recipient` for the recipient, `rejected` otherwise) rather than raised,
  so notification never retries a message that cannot be built.
- `contracts/port.yaml` corrected to match the implementation and its only caller: the sending identity is
  `sender`, not `from` (a Python keyword, so no implementation could take it, and nothing ever did). Added the
  optional `reply_to`, `retry_after_s` and `supports_reply_to`, and defined `rate_limit_per_minute: 0`. Kept at
  version 1, since no consumer was ever built against `from`.
- Discovery by entry point: `eos.outbound_messaging` → `messaging-providers`, so `platform/notification` finds
  this adapter without importing it. SMS and WhatsApp fail closed until a provider exists.
- Operator API (contract 0.2.0): `GET /providers`, `GET /providers/{provider}/health` and
  `POST /providers/{provider}/test`. The first two need `messaging-providers:provider:read`, the test send
  `platform:messaging-providers:admin`. No credential or host is ever returned. Health never sends. A test send is
  capped by `MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR` per process, counts refused attempts, and is recorded on the
  `eos.messaging_providers.audit` log, never with the address, until platform/audit exists. Additive: a 404 on an
  unknown provider for the test send, and `supports_reply_to` in a provider's capabilities.
- Enabled in the host: listed under `integrations:` in `apps/backend/config/modules.enabled.yaml`, so it is
  installed wherever the API runs and the operator API is mounted at `/api/v1/messaging-providers`.
  `messaging-providers` joins `PLATFORM_MODULES` so the entitlement gate passes its super-admin callers to the
  route's own permission check.
- `contracts/permissions.yaml`: the `messaging-providers-operator` block is removed. Blocks are named with platform
  role ids and no profile assigns that one, so it granted nothing; only `super-admin` holds the two keys.
- `super-admin` role added to `contracts/permissions.yaml`. A super admin is given only the `platform:` keys that
  some role grants, and none granted `platform:messaging-providers:admin`, so nobody could hold it.
- Not yet: webhook intake and normalised receipts (SMTP reports nothing by webhook, so there is nothing to receive
  until a provider like SES or SendGrid exists), and the three events in `contracts/events.yaml`, which need an
  outbox write this module has no database session for.
- Week 1: OutboundMessaging port, webhook intake, events and permissions proposed (contracts only).
