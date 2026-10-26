# One idempotency contract for notification

**Status:** awaiting approval. The code, the tests and the README already match this text, so approving it
changes nothing and rejecting any rule is a contained edit. Nothing is committed or pushed.
**Author:** Himanshu (@himanshu-rooman). **Reviewer:** Faizan.
**Blocks:** issue #79 review (blocker B2). **Related:** #83 (event relay and handler interface).

## Why this exists

The service has two idempotency keys today: `client_token`, supplied by the caller, and `source_event_id`,
supplied by a future relay. Each has its own unique constraint and its own lookup path in `accept_message`.
Two keys mean two definitions of "the same request", two ways to be wrong, and a replay check whose answer
depends on which key the caller happened to use. This proposes one key.

## The contract

1. **`client_token` is the only idempotency key.** It is the sole thing that decides whether a send is a repeat.
   One unique constraint backs it: `(organisation_id, client_token)`.

2. **An event-linked send derives its token** instead of being given one:

   ```
   client_token = "evt:" + sha256("<source_event_id>|<template_key>|<channel>|<recipient_key>")
   ```

   joined with `|`, hex digest, 68 characters, inside the existing 120-character limit. `recipient_key` is the
   recipient **as the caller asked** (`user_id`, else lower-cased address) — never the resolved recipient, which
   depends on state that can change between deliveries.

3. **A supplied token that disagrees with the derived one is a 422.** If a caller passes both a
   `source_event_id` and a `client_token` that is not the derived value, that is a programming error in the
   relay, not a send; it is refused rather than silently preferring one key.

4. **`channel` stays required for an event-linked send** (422 without it). One event may notify one person on
   several channels; with the channel left to preferences, a redelivery cannot tell "the same message again"
   from "the same event on another channel". This is today's behaviour and does not change.

5. **`source_event_id` remains a stored column and keeps its unique constraint
   `(organisation_id, source_event_id, template_key, channel, recipient_key)` — as a safety net only.** It is
   recorded for tracing and it still backstops a race at the database. Nothing reads it to decide whether a send
   is a repeat: the replay decision is `client_token` alone. The single remaining read is in `_find_duplicate`,
   recovering the existing row if that constraint fires, because a constraint that exists must be handled.

6. **The event receipt table is out of scope.** A receipt keyed `(organisation_id, event_id, handler)` is the
   right answer to "a handler recomputes its recipients on redelivery and reaches a member who joined since",
   but it belongs with the handler interface. It is deferred to the **#83 design review**, and until it exists
   the limit stands and is documented as such.

## What this does and does not fix

Fixed: one key, one definition of "same request", one constraint to reason about, and a relay that no longer
needs to know a second dedupe mechanism exists.

Not fixed: a handler that works out its recipients at handling time (for example "every org admin") can still
send to a member added between deliveries — the derived token covers a different recipient, so it is a new
message. That needs the receipt from #83. This proposal does not claim otherwise.

## The one decision to confirm

Under rule 2 an event-linked send now has a `client_token`, so it also gets a `request_hash` and therefore the
"same token, different request" check. Previously an event-linked send had no token, no hash and no such check.

So **a redelivery of the same event whose variables differ from the first delivery is now a 422** where it used
to return the existing message. I have implemented the 422, because identical event, identical template and
identical recipient with different content means the relay or the producer is broken, and a silent return hides
it. The cost is that a relay bug surfaces as an error response rather than a no-op.

To take the other answer instead, stop computing a fingerprint for a derived token in `accept_message`; the
test `test_an_event_redelivery_whose_variables_changed_is_refused` in `tests/test_send.py` then inverts. That is
the whole change.

## What changed (done locally, not committed)

| Area | Change |
|---|---|
| `application/messages.py` | derive the token when `source_event_id` is given; 422 on a conflicting supplied token; delete the `source_event_id` replay lookup and its branch in `_find_duplicate` |
| `domain/models.py` | no column changes; the event unique constraint stays, with its comment demoted to "safety net" |
| `db/migrations/` | **no new revision needed.** No column changed; `notification_0001` has never been committed, so it could still be amended in place if that changes |
| `contracts/openapi.yaml` | document that a caller must not supply `client_token` alongside an event-linked send |
| `README.md` | replace "Idempotency today" and the "Proposed, not implemented" paragraph with this contract; keep the known limit, pointing at #83 |
| tests | five added in `tests/test_send.py`: the derived value and its length, a conflicting supplied token, the derived token supplied explicitly, a redelivery with changed variables, and that derivation keys off the recipient as asked. Each was checked against a mutation of the rule it covers |

## Acceptance criteria (blocker B2)

- [ ] This text approved by Faizan, including the decision above — **outstanding**
- [x] Code matches it, with the `source_event_id` replay path removed
- [x] README states this contract and no longer calls it proposed
- [x] Tests cover each rule, and the suite passes (152 tests, SQLite only — see B4 for PostgreSQL)
