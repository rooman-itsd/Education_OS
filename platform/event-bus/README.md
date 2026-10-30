# event-bus

**Domain:** platform
**Kind:** platform
**Status:** in progress — relay with the in-process transport, operator API

Domain event contracts and broker abstraction. The only async channel between modules.

## Scope
A module announces that something happened by calling `eos_core.events.publish()` inside its own transaction;
this module delivers it to every module that consumes it. It owns the event envelope
([contracts/events.yaml](contracts/events.yaml)), the relay that drains `outbox_event`, the table's DDL (its
Alembic chain), and the operator view of the outbox. It is not a permanent record (`platform/audit`), not a
job runner (`platform/scheduler`), and does not deliver outside Education OS (`integration-hub`). Design:
[docs/outbox-relay.md](docs/outbox-relay.md).

## What this release provides

| Piece | State |
|---|---|
| `outbox_event` owned by this chain: 0001 creates it as `eos_core` always did (and is only recorded on a database that has it); 0002 adds `version`, `attempts`, `last_error`, `published_at`, `next_attempt_at` and the `(published, occurred_at)` index | built; head checked against the model column for column |
| Relay pass: claim oldest first (`FOR UPDATE SKIP LOCKED` on Postgres), deliver, mark published | built, tested; claim and isolation checked on PostgreSQL as `eos_app` |
| Retries with exponential backoff (1 s doubling, capped by `EVENT_BUS_RETRY_CAP_S`); dead letter after `EVENT_BUS_MAX_ATTEMPTS`, announced by `event-bus.event.dead-lettered` | built, tested |
| `event-bus.relay.stalled` once per stall; pruning of delivered events after `EVENT_BUS_RETENTION_DAYS` (pending and dead-lettered rows are kept) | built, tested |
| In-process transport: consumers found on the `eos.event_consumers` entry-point group; each runs in its own transaction, in the event's organisation, with row-level security on | built, tested |
| Operator API: `GET /events`, `GET /events/{id}`, `POST /events/{id}/replay`, `GET /relay/health` | built, tested, cross-tenant leak test |
| `python -m eos_event_bus`: the relay as its own process, until SIGTERM | built |

## Consuming an event

```toml
# <your module>/backend/pyproject.toml
[project.entry-points."eos.event_consumers"]
billing = "eos_billing.application.consumers:CONSUMERS"
```

```python
# eos_billing/application/consumers.py
def on_job_due(db: Session, event: Event) -> None:  # eos_event_bus.domain.models.Event
    ...


CONSUMERS = {"scheduler.job.due": on_job_due}
```

The handler gets its own session, already in the event's organisation (platform scope for a platform-level
event), and the relay commits it. **It must be idempotent on `event.id`**: delivery is at-least-once, and if any
consumer of an event fails, the event is retried for every consumer. A failure is recorded as
`<module>: <exception type>`, never the exception text, which can carry the payload's personal data.

## What this release does NOT do

1. **Nothing runs the relay in a deployment yet.** `python -m eos_event_bus` is the process; the compose stack
   needs a service for it (`infra/`). Until then events are recorded and delivered to nobody.
2. **No broker transport.** `EVENT_BUS_TRANSPORT` accepts only `inprocess`; Redis Streams follows the broker ADR.
3. **No audit record of a replay**: `platform/audit` is not built yet, so a replay is recorded on the
   `eos.event_bus.audit` log.
4. **Dead-lettered is derived from `EVENT_BUS_MAX_ATTEMPTS`.** Raising the limit returns dead-lettered events
   to pending; lowering it dead-letters pending ones without a notice.
5. **The stall notice is per process.** Two relays may each raise one for the same stall.

## Migrations and existing databases

The relay columns live on `eos_core.events.OutboxEvent` (packages/core), so the model and this chain change
together. On a database where the API already created `outbox_event`, 0001 is recorded without running and
0002 adds the columns; every row already there is marked published, because no consumer existed when it was
written and delivering weeks of history at once would act on stale events.

## Configuration

Every key is in [config/env.example](config/env.example), prefixed `EVENT_BUS_`, each bounded: a value out of
range stops the relay at start rather than spinning or never dead-lettering.

## Tests

```
pytest platform/event-bus/backend/tests -q
```

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
