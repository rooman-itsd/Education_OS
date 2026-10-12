# Outbox relay — design

Status: proposed, week 1 (issue #61). Owner: Himanshu (@himanshu-rooman).
Reviewer: Faizan (@faizanrooman), because it asks for a change to `packages/core`.

This is the design for the missing half of the transactional outbox. It is written here rather
than as an ADR because `docs/architecture/` is the architecture lead's. If the transport decision
below is accepted, it should become an ADR; the broker choice is listed as pending in
`ARCHITECTURE.md`.

## The problem

A module must not publish an event unless its state change committed, and must not commit a
state change without publishing the event. Two systems (database and broker) cannot be written
atomically, so we write only to the database and move the event afterwards. That is the
transactional outbox, already decided in ADR-0002 ("Postgres outbox mandatory").

## What already exists

`packages/core/src/eos_core/events.py` has the **write side**:

```python
class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    id, organisation_id, name, actor, payload, occurred_at, published

def publish(session, name, organisation_id, payload, actor=None) -> OutboxEvent
```

Modules call `publish()` inside their own transaction. The row commits with the state change,
or neither does. Its docstring already names the missing half:

> a relay (platform/event-bus) moves rows to the broker

Nothing drains `outbox_event` today. **That relay is this document.**

## The decision

**The relay is broker-agnostic.** It reads the outbox and hands batches to a *transport*,
which is a port with swappable implementations. No module, anywhere, ever talks to a broker;
the dependency rules in `ARCHITECTURE.md` already forbid it. Only the relay does.

This is deliberate: the event broker is still an open decision. Making the relay broker-agnostic
means that decision no longer blocks anyone. Week 1 ships the port and an in-process transport;
a later ADR picks Redis Streams, RabbitMQ or Kafka and adds one class, touching no module.

```
module.publish()  ->  outbox_event  ->  [ relay ]  ->  transport  ->  consumers
   (in its txn)       (Postgres)       (this module)   (pluggable)
```

### The transport port

```python
class Transport(Protocol):
    def deliver(self, events: list[Event]) -> list[str]:
        """Deliver events. Return the ids accepted. Raise to retry the whole batch."""
```

| Transport | When | Status |
|---|---|---|
| `inprocess` | Modular monolith (the default deployment shape). Delivers to subscribers registered in the same `apps/backend` process | Week 2 |
| `redis-streams` / `rabbitmq` / `kafka` | Grouped services or dedicated instances | After the broker ADR |

`EVENT_BUS_TRANSPORT` selects one. Default `inprocess`, which needs no new infrastructure and
keeps the single-deployment default of ADR-0005 working on day one.

### The loop

1. Claim a batch: oldest unpublished rows, `ORDER BY occurred_at, id`, `LIMIT batch_size`,
   with `FOR UPDATE SKIP LOCKED` so several relay workers can run without doubling up.
2. Set `app.organisation_id` from the envelope before invoking each consumer, so row-level
   security applies to consumer writes exactly as it does to API requests.
3. Hand the batch to the transport.
4. Mark accepted ids `published = true`, `published_at = now()`.
5. On failure, increment `attempts`, record `last_error`, and retry with exponential backoff
   (1s, 2s, 4s … capped). After `EVENT_BUS_MAX_ATTEMPTS` the row is dead-lettered and
   `event-bus.event.dead-lettered` is raised. Dead-lettered rows are never retried
   automatically; an operator replays them through the API.
6. Sleep `EVENT_BUS_POLL_INTERVAL_MS` when the outbox is empty.

Polling, not `LISTEN/NOTIFY`: notifications are not durable, so a missed one loses an event.
Polling is dull and correct, and the interval is small enough that latency is not a concern.

### Guarantees

- **At-least-once.** A crash between delivery and step 4 redelivers. Consumers must be
  idempotent on `envelope.id`; this is stated in `contracts/events.yaml` and is not optional.
- **No ordering guarantee.** `SKIP LOCKED` and retries both reorder. A consumer that needs
  order must use the entity's own state.
- **No cross-tenant delivery.** `organisation_id` rides on the envelope and is set as the
  session variable before the consumer runs.

## Required change to `packages/core` (owner: Faizan)

`OutboxEvent` cannot support retry or dead-lettering as it stands. The relay needs four columns
and one index added to `packages/core/src/eos_core/events.py`:

| Column | Type | Why |
|---|---|---|
| `version` | int, default 1 | On the envelope in `contracts/events.yaml`; no column exists for it today |
| `attempts` | int, default 0 | Backoff and the dead-letter threshold |
| `last_error` | text, null | Diagnosis without reading logs |
| `published_at` | datetime, null | Relay lag, and the `event-bus.relay.stalled` signal |

Plus `INDEX (published, occurred_at)` — the claim query in step 1 runs constantly and scans
the table without it.

I cannot make this change: `packages/` is the architecture lead's. **It is the one hard
dependency in this design** and is why the week-1 deliverable is the design, not the relay.

## Operating it

| Setting | Default | Meaning |
|---|---|---|
| `EVENT_BUS_TRANSPORT` | `inprocess` | Which transport |
| `EVENT_BUS_POLL_INTERVAL_MS` | `1000` | Idle poll interval |
| `EVENT_BUS_BATCH_SIZE` | `100` | Rows per claim |
| `EVENT_BUS_MAX_ATTEMPTS` | `8` | Then dead-letter |
| `EVENT_BUS_STALL_THRESHOLD_S` | `300` | Oldest unpublished age that raises `relay.stalled` |

The relay runs as an `arq` worker (the approved job runner) beside `apps/backend`. In the
monolith it may run in-process; at scale it is a separate process reading the same table.

## What this does not do

- It does not deliver to external systems. Outbound webhooks are `integration-hub`'s.
- It does not store events forever. Published rows are pruned on a retention window
  (`platform/audit` is the permanent record, not the outbox).
- It is not a queue for work. Scheduled and deferred work is `platform/scheduler`.

## Open questions for review

1. **`version` on the envelope** — kept here, and already assumed by
   `modules/sports/training-video-analysis`, but there is no column for it. Confirm before
   modules start publishing; it cannot be retrofitted cheaply.
2. **Retention** — how long do published rows stay? Proposed 30 days.
3. **Replay scope** — should an operator be able to replay an already-published event, or only
   a dead-lettered one? This contract allows only dead-lettered, as replaying a delivered event
   re-triggers every consumer.
