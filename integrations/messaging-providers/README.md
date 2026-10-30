# messaging-providers

Email, SMS and WhatsApp provider adapters. Implements the **OutboundMessaging** port
([`contracts/port.yaml`](contracts/port.yaml)), so `platform/notification` depends on the port and never on a
vendor: changing provider is configuration, not code.

**Status:** email over SMTP is implemented and exercised against a real server. SMS and WhatsApp are
contracted only.

## What this release provides

| Piece | State |
|---|---|
| `OutboundMessaging` port types, version 1, exactly as `port.yaml` defines them | built (`domain/port.py`) |
| SMTP email provider: `send`, `capabilities`, `healthcheck` | built (`infrastructure/smtp.py`) |
| Every SMTP failure mapped to one of the four port reason codes, with a retryable flag | built, 11 cases tested |
| `reply_to`, advertised through `capabilities().supports_reply_to` | built, tested |
| Provider registry: channel → provider by environment, failing closed | built (`application/registry.py`) |
| Credentials from the environment only, never in `repr()`, a log line or an error | built, tested |
| Operator API: list providers, provider health, rate-limited test send (`api/router.py`) | built, tested; mounted at `/api/v1/messaging-providers`, super admin only |
| 65 tests: 62 against a fake server, 3 that need a real one | 62 pass; the 3 skip unless a server is configured |

## What this release does NOT do

1. **Notification does not send through it until notification is enabled and configured.**
   `platform/notification`'s `AdapterTransport` finds it by entry point, not by import; notification is enabled
   by PR #300, and selects this adapter with `NOTIFICATION_TRANSPORT=adapter`. See "Wiring" below.
2. **No SMS and no WhatsApp.** Named in `port.yaml` and `config/env.example` so the shape is agreed. Asking
   the registry for either raises `ProviderUnavailableError` rather than returning something that accepts a
   message and drops it.
3. **No attachments.** `send()` refuses them (`rejected`) rather than dropping them silently; they need
   `platform/documents` to fetch the file.
4. **No inbound receipts.** `port.yaml` defines the webhook shape and `domain/port.py` carries the `Receipt`
   type, but there is no endpoint, no signature verification and no event. So nothing records `delivered` or
   `bounced`, and a hard bounce does not suppress an address.
5. **No webhook intake.** Three of the four operations in `contracts/openapi.yaml` are built and mounted;
   `POST /webhooks/{provider}` is not, because SMTP reports nothing by webhook. The three events in `contracts/events.yaml` are not published: each needs an outbox write, and this module
   has no database session to make one.
6. **No `retry_after_s`.** SMTP has no retry-after signal, only reply text, which this module never trusts. It
   is always null, and notification falls back to its own backoff.
7. **Not proven against a commercial relay.** See "Delivery evidence".

## Delivery evidence

Exercised against **MailHog**, a real SMTP server, on 15 Oct 2026 — not a fake, not a mock:

```
docker run -d --name eos-mail -p 1026:1025 -p 8026:8025 mailhog/mailhog
EOS_LIVE_SMTP_HOST=localhost EOS_LIVE_SMTP_PORT=1026 \
  pytest integrations/messaging-providers/tests/test_live_smtp.py -v
→ 3 passed
```

The messages arrived, with the correlation header intact:

```
To: live@college.example.com | Subject: Verify your Education OS organisation
X-EOS-Message-Id: 11111111-1111-1111-1111-111111111111
Body: Welcome to Rooman. Verify with token abc123
```

**The third live test has changed since that run.** It used to assert that the reason was any port code or
none — every value a result can hold, so it could not fail. It now checks that the recipient never reaches a
log line, and that a refusal reads as a bad recipient rather than a retryable failure. That version has not yet
run against a real server; until it has, the 15 Oct result covers only the first two.

**What that does and does not prove.** It proves the adapter speaks SMTP correctly to a real server: it
connects, builds a well-formed message, sends, and reads the reply. It does **not** prove production
delivery. MailHog is a mail *catcher* — it accepts everything, authenticates nobody and forwards nothing. Not
yet exercised: TLS, authentication against a real relay, a real rejection or bounce, and anything a
commercial provider does differently. **Do not read "delivery works" into this** until it has run against the
relay staging will actually use.

## Safety rules this module keeps

- **A log line never carries the body, the recipient or the subject.** It carries the message id, the
  provider (`host:port`, never a credential), the outcome and a port reason code. Tested.
- **A provider's own text never leaves the module.** SMTP errors routinely echo the address back; only the
  four port codes are returned, so notification cannot store provider prose. Tested.
- **`send()` takes named parameters and no `**kwargs`.** notification's `OutboundMessage` carries
  `dev_secrets`, an in-process-only carrier for a verification token. The port has no such field, so passing
  it — or splatting the whole dataclass — is a `TypeError` at the boundary rather than a secret reaching a
  provider. That is issue #80's main hazard, closed by construction rather than by remembering. Tested both ways.
- **A header with a line break is refused, never sent and never retried.** That is what stops header
  injection, through `to`, `reply_to`, `sender` or `subject`. It comes back as a permanent refusal rather
  than an exception, so notification does not retry a message that can never be built. Tested.
- **Credentials come only from the environment**, are excluded from `repr()`, and `describe()` is the only
  provider string that may be logged. `config/env.example` is asserted to hold no real password.

## Wiring

`platform/notification` never imports this module. Its `AdapterTransport` looks the adapter up on the
`eos.outbound_messaging` entry-point group by the name in `NOTIFICATION_ADAPTER` (default
`messaging-providers`, which `pyproject.toml` declares), maps the message onto `send()` field by field, and
leaves `dev_secrets` out. So there is **no dependency to add to notification**, and adding one would break the
boundary the entry point exists to keep.

What it does need is this package installed wherever notification runs; without it, notification answers 503
rather than guessing a provider. It is listed under `integrations:` in `apps/backend/config/modules.enabled.yaml`,
so `tools/scripts/py-setup.sh`, CI and the API image install it, and the host mounts the operator API at
`/api/v1/messaging-providers`.

The operator API is platform-level: its two keys are granted only to `super-admin`, who has no organisation.
`messaging-providers` is therefore in `PLATFORM_MODULES` (`packages/core/src/eos_core/entitlement.py`), so the
host's entitlement gate lets the request through to the route's own permission check instead of refusing every
caller without an organisation. `apps/backend/tests/test_messaging_providers_mount.py` checks both through the
real host.

## Tests

```
pytest integrations/messaging-providers/tests -q          # 62 passed, 3 skipped (no live server)
```

The live tests skip unless `EOS_LIVE_SMTP_HOST` is set; their other settings are listed at the end of
[`config/env.example`](config/env.example). Everything else uses a fake SMTP server that can be told to raise
any `smtplib` exception, so all 11 error branches are covered without a server that misbehaves on demand.

## Configuration

Every key is in [`config/env.example`](config/env.example), prefixed `MESSAGING_PROVIDERS_`. Defaults point at
a local MailHog so a developer sends real-looking mail with no account anywhere. **Never commit a real value.**
