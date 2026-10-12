# notification — PRD

Owner: Himanshu (@himanshu-rooman) · Tier: core · Status: planned

## What this is

Everything Education OS sends to a person: email, SMS, WhatsApp, push and in-app.
A module says *who* to tell and *what about*; this service decides the channel, renders the
template in the recipient's language, respects their preferences, sends it, and records
whether it arrived.

**This service already has a live stand-in.** `packages/core/src/eos_core/notify.py` is a stub
that appends to an in-memory list and logs, labelled *"until platform/notification ships"*.
`platform/tenancy` calls it today to send organisation verification mail. Replacing that stub
is this module's first job, and it has two constraints that are easy to miss (below).

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| The physical connection to an email, SMS or WhatsApp provider | `integrations/messaging-providers`. This module picks a message and a recipient; the adapter puts it on the wire |
| Deciding *when* something should be sent later | `platform/scheduler`. It wakes up and asks this module to send |
| The record that a thing happened | `platform/audit` |
| Announcements between modules | `platform/event-bus`. Events are for software, notifications are for people |
| Document generation or storage | `platform/documents`. Attach by document id |
| Marketing campaigns, bulk mail, newsletters | Out of scope for the product |

The distinction that matters: **an event is consumed by code, a notification is read by a
human.** `billing.trial.expired` is an event. "Your trial ends on Friday" is a notification.
This module turns the first into the second.

## Two constraints when replacing the stub

1. **`packages/testing` reads the stub.** `eos_testing.register_and_login` pulls the
   verification token out of `notify.sent`. Every foundation test depends on it. The stub
   cannot simply be deleted; it has to keep working as the test and dev-mode transport, which
   this contract preserves as the `memory` channel backend.

2. **The current call sends before it commits.** In
   `eos_tenancy/application/service.py`, `notify.send_email(...)` runs *before* `db.commit()`.
   If the commit fails, the person has already been told their organisation exists. The fix is
   not to reorder the lines but to stop sending inline: a module should record the intent in
   the same transaction and let this service send after the fact. That is exactly what the
   outbox already does for events, so notification consumes events rather than being called
   synchronously wherever possible.

## The flows it must serve first

From the registration flow in `ARCHITECTURE.md`, with the real event names published today:

| Event (already published) | Notification |
|---|---|
| `tenancy.organisation.registered` | Verify your email — carries the token. **Replaces the one live `send_email` call** |
| `tenancy.organisation.verified` | Awaiting approval by the platform operator |
| `tenancy.organisation.approved` | Your academy is live; here is how to sign in |
| `tenancy.package.requested` / `.changed` | Package change requested / approved |
| `billing.subscription.started` | Trial started, what it includes, when it ends |
| `billing.trial.expired` | Trial ended, how to upgrade |
| `billing.subscription.upgraded` | Plan changed, what is now available |
| `identity.user.created` | Welcome, set your password |

Trial *reminders* ("ends in 3 days") have no event, because nothing has happened yet. Those
come from `platform/scheduler` calling this module.

## Users

| Who | Needs |
|---|---|
| Every module | One call, or one event, and the person gets told. No channel logic in module code |
| Any recipient | Messages in their language, on channels they chose, with a way to stop |
| Organisation Admin | Branding and templates for their own academy; what was sent and whether it arrived |
| Super Admin | Platform-wide delivery health and failures |

## Rules

- **Tenant-scoped.** Every message, template and preference carries `organisation_id` with RLS.
  An organisation's template can never render for another's recipient.
- **Preferences are honoured, except for transactional mail.** Verification, password reset and
  security notices are always sent; a person cannot opt out of being told their account changed.
  Everything else is opt-out.
- **Idempotent.** Sends are keyed on `client_token`, so a retried request or a redelivered
  event cannot send the same message twice. This matters because event delivery is
  at-least-once by design.
- **Never log message bodies.** They contain personal data and sometimes tokens.
- **Email first.** SMS, WhatsApp, push and in-app are in the contract so modules can write
  against them, but only email is implemented in week 2.

## Scope, week by week

| When | What |
|---|---|
| Week 1 (this) | Contracts, PRD, the template and preference model |
| Week 2 | Backend, email channel, the registration and trial mails, replacing the stub |
| Later | SMS and WhatsApp through the adapter, in-app inbox and its widget, per-academy branding, digests |

## Dependencies

- **`integrations/messaging-providers`** — the actual transport. Mine; contracted in the same week.
- **`platform/event-bus`** — most sends are reactions to events.
- **`platform/scheduler`** — reminders and digests.
- **`platform/identity`** — recipient addresses, language, permission checks.
- **`platform/documents`** — attachments, by id.
- **`packages/sdk`** — how modules call this. Empty today, and the architecture lead's.

## Success

- No module contains channel logic, provider credentials or an email template.
- A rolled-back transaction never results in a sent message.
- A person never receives the same notification twice from one cause.
- Replacing the stub breaks no existing test.

## Open questions for review

1. **Does a module call this, or publish an event this consumes?** Proposed: prefer events, so
   nothing is sent for work that did not commit. A direct call stays for the cases with no
   natural event (a reminder, an operator resending).
2. **Who owns templates?** Platform defaults, overridable per organisation. Proposed: yes, with
   the platform default as fallback so a new academy sends sensible mail on day one.
3. **In-app inbox** — this module, or a widget each module provides? Proposed: this module owns
   the inbox and ships one widget; otherwise every module reinvents it.
