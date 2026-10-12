# messaging-providers — PRD

Owner: Himanshu (@himanshu-rooman) · Kind: integration · Tier: common · Status: planned

## What this is

The physical connection between Education OS and the companies that actually carry a message:
SMTP and email services, SMS gateways, the WhatsApp Business API.

It is the last hop. `platform/notification` decides *who* is told *what*, renders it and
records it. This adapter takes a rendered message and puts it on the wire, then reports back
what the provider said.

**Email first.** SMTP is the only provider implemented in week 2, because it is what the
registration flow needs and it works against a local mail catcher with no account anywhere.
The rest are contracted ahead so nothing has to be redesigned to add them.

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| Deciding what to send, to whom, or in which language | `platform/notification` |
| Templates, preferences, quiet hours, opt-outs | `platform/notification` |
| Retry policy and the delivery history a human reads | `platform/notification`. This adapter retries only transport-level failures |
| Choosing a channel | `platform/notification` |
| Inbound replies as a conversation | Out of scope. Inbound is limited to delivery receipts and bounces |

`ARCHITECTURE.md` places adapters behind `platform/integration-hub` and allows them to import
only `packages/` and implement hub ports. This adapter never calls a business module, and no
business module ever calls it: traffic arrives from `notification` alone.

## The port it implements

One port, `OutboundMessaging`, defined in [../contracts/port.yaml](../contracts/port.yaml):

```
send(message)   -> accepted, provider_message_id | rejected, reason
capabilities()  -> channels, max body size, attachment support, rate limit
healthcheck()   -> reachable
```

Every provider implements the same three operations. `notification` depends on the port, never
on a provider, so swapping SendGrid for SES is configuration.

## Providers

| Provider | Channel | When |
|---|---|---|
| `smtp` | email | Week 2. Works against a local catcher (MailHog) with no account |
| `ses`, `sendgrid` | email | When a real sending domain exists |
| `twilio`, `msg91` | sms | After email |
| `whatsapp-cloud` | whatsapp | Last; needs template pre-approval by Meta, which is a lead time, not a task |

## Credentials and tenancy

- **No secrets in git, ever** (team rule 10). `config/env.example` carries key *names* and
  obviously fake values. Real values arrive as environment variables.
- Provider credentials are **platform-level, not per organisation**. One sending identity
  serves every academy in a deployment; a per-organisation sending domain is a later feature
  and would need DNS verification per tenant.
- Messages still carry `organisation_id` so delivery receipts can be attributed back, and so
  rate limits and suppression can be reasoned about per academy.

## Inbound

Providers report what happened asynchronously, by webhook: delivered, bounced, complained.
The adapter exposes one webhook endpoint per provider, verifies the signature, normalises the
vendor's payload into one shape, and publishes it. `notification` consumes that and updates
the message.

A webhook that cannot be verified is rejected, never processed. This endpoint is public by
necessity, so signature verification is the only thing standing in front of it.

## Scope, week by week

| When | What |
|---|---|
| Week 1 (this) | Contracts, the port definition, the PRD, config keys |
| Week 2 | SMTP provider, the send path, webhook intake, normalised receipts |
| Later | SES/SendGrid, SMS, WhatsApp, per-organisation sending domains |

## Dependencies

- **`platform/integration-hub`** — owns the port and the adapter registry. Mine.
- **`platform/notification`** — the only caller. Mine.
- **`platform/audit`** — credential changes and test sends are recorded.

## Success

- `notification` contains no provider names, SDKs or credentials.
- Adding a provider is one class plus config, touching no other module.
- A local developer sends real-looking mail with no account anywhere.
- No credential ever appears in the repository.

## Open questions for review

1. **Per-organisation sending identity.** Proposed: not in v1. It needs DNS verification per
   tenant, which is an operational process, not a code change.
2. **Webhook routing.** Providers post to one URL for the whole deployment, so the adapter must
   map a receipt back to an organisation via `provider_message_id`. Confirm that is acceptable
   rather than issuing per-tenant webhook URLs.
3. **Rate limiting.** Whose job is it when a provider throttles — this adapter backing off, or
   `notification` queueing? Proposed: the adapter reports the limit through `capabilities()`
   and signals throttling; `notification` owns the queue.
