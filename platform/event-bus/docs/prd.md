# event-bus — PRD

Owner: Himanshu (@himanshu-rooman) · Tier: core · Status: planned

## What this is

The only asynchronous channel between modules. A module announces that something happened;
other modules react. Neither knows the other exists.

`ARCHITECTURE.md` forbids module-to-module code imports, so the bus is not a convenience —
it is one of the two ways modules may interact at all (the other is a call to a published
OpenAPI contract through the gateway).

Concretely, this module owns three things:

1. **The event envelope** — the shape every event in Education OS carries. Defined in
   `contracts/events.yaml`, inherited by all 56 modules.
2. **The relay** — the process that drains `outbox_event` and delivers to a transport.
   Designed in [outbox-relay.md](outbox-relay.md).
3. **Operator visibility** — read the backlog, inspect an event, replay a dead-lettered one.

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| A permanent record of what happened | `platform/audit` — immutable, queryable, kept. The outbox is a delivery buffer and is pruned |
| A work queue, cron, or deferred-job runner | `platform/scheduler` |
| Delivery to systems outside Education OS (webhooks, third-party APIs) | `platform/integration-hub` and `integrations/*` |
| A request/response channel | The module's own `contracts/openapi.yaml`, through the gateway |
| A place to put large documents or media | `platform/documents`; put an id in the payload |
| The thing that decides whether a module is switched on | The entitlement (`platform/tenancy`). The bus delivers to consumers that are present; a module that is off simply has no consumer |

The bus carries facts, never commands. `fees-accounts` subscribing to
`admissions.application.accepted` is correct; an event named `fees-accounts.invoice.create`
is not — that is a command, and it should be an API call.

## Why it matters first

Every module publishes events, so every module's `contracts/events.yaml` inherits this
envelope. Nine other owners are writing those files in week 1. If the envelope lands late or
changes afterwards, their work is redone.

One field in particular, `version`, cannot be added cheaply once modules are publishing — a
consumer that has never seen a version cannot be told later which schema it was reading.

## Users

This module has no end-user screens. Its consumers are other modules; its human users are
operators.

| Who | Needs |
|---|---|
| Every module (as publisher) | `eos_core.publish()` in its own transaction, and an envelope it does not have to think about |
| Every module (as consumer) | Events delivered at-least-once, scoped to one organisation, with a stable payload contract |
| Super Admin | Backlog health, dead-letter queue, replay. Surfaces on the Super Admin dashboard |
| Platform operator | Relay lag and stall alerts |

## Scope, week by week

| When | What |
|---|---|
| Week 1 (this) | The envelope, the relay design, the ops API contract, permissions |
| Week 2 | The relay itself, the `inprocess` transport, dead-lettering, the ops endpoints |
| Later | A broker transport once the broker ADR lands; retention and pruning; a Super Admin widget |

## Dependencies

- **`packages/core`** — owns `outbox_event` and `publish()`. This design needs four columns
  and an index added to it; that is the architecture lead's change, and it is the one hard
  dependency. See [outbox-relay.md](outbox-relay.md#required-change-to-packagescore-owner-faizan).
- **`platform/identity`** — permission checks on the ops API.
- **`platform/audit`** — a replay is an operator action and is audited.

## Success

- A module author never writes delivery code: `publish()` in a transaction is the whole job.
- No event is lost when a consumer, the relay or the broker is down.
- No event ever crosses an organisation boundary.
- Choosing a broker later changes one class in this module and nothing anywhere else.
