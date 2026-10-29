# budget-grants: atomic commitments for procurement (proposal, v2)

Status: **design approved in direction by the module owner (29 Oct), not implemented.** Issue: #335 (was #129;
risk 1 in #295). Owner: Gokula Lakshmi (budget-grants and procurement). Reviewer: Ashritha. Architecture review:
Faizan (cross-module contract and migration). The overspend risk stays **open** until the delivery below is merged
and its concurrency tests pass.

v2 answers the review on #350:
- every money change procurement makes is synchronous, so nothing waits for the relay;
- reservations record `purchase_order_id`;
- reservations live in their own append-only table, which has every column the API needs;
- nothing is reactivated or rewritten;
- the trust boundary is a recorded decision.

## The problem, reproduced

A line's available amount is checked in two places that do not see each other:

- **Manual spend** (`POST /expenditures`) locks the budget-grants line row and checks what budget-grants has recorded.
  Payroll locks the row and always records.
- **Procurement order approval** checks `GET /availability`, then issues the order. budget-grants learns about the order
  only when the `procurement.purchase-order.issued` event arrives. procurement's per-line advisory lock covers only
  procurement.

Reproduced on PostgreSQL 16 as a non-superuser, both modules mounted in one app: a line with 2000.00, an order of
1180.00 and a manual spend of 1180.00. Both were accepted and the line ended at **available -360.00**, whether the
event arrived late or instantly.

## The fix in one sentence

Every change procurement makes to a line's money is a **synchronous call to budget-grants**:
- reserving the order total at approval;
- confirming at issue;
- releasing at return, cancellation or close;
- turning the commitment into spend when an invoice is paid.

budget-grants checks and records each one in one transaction, under the same line-row lock manual spend and payroll
take. A reservation counts against the line from the moment it is recorded.

## Storage: an append-only commitments table

A new table `budget_grants_commitment`. Like every table, it has `organisation_id` and the forced `tenant_isolation`
row-level-security policy. Migration `budget_grants_0002` creates it.

| Column | Type | Notes |
|---|---|---|
| `id`, `organisation_id` | String(36) | |
| `line_id` | String(36), FK line | |
| `source_module`, `source_reference` | String(30), String(120) | `procurement` and the purchase order id |
| `purchase_order_id` | String(36), indexed | always set; how the existing payment and cancellation code finds an order's commitment |
| `amount` | Numeric(14, 2) | the reserved order total |
| `state` | String(10) | `reserved`, `committed`, `released` |
| `reserved_at`, `reserved_by` | DateTime, String(36) | |
| `confirmed_at`, `confirmed_by` | DateTime, String(36), nullable | |
| `released_at`, `released_by`, `release_reason` | DateTime, String(36), Text, nullable | |

- **Append-only lifecycle.** A row moves `reserved → committed` or `reserved → released`, and never back.
  - A released row is never reactivated.
  - Reserving the same order again, after a return, inserts a **new** row, so the history of every attempt stays.
  - Amount, line and source never change after insert.
- **Idempotency key.** At most one *live* row (`reserved` or `committed`) per `(organisation_id, source_module,
  source_reference)`, enforced by a partial unique index (`WHERE state IN ('reserved', 'committed')`; Postgres and
  SQLite both support it). Released rows don't count towards the key.
- **The ledger stays as it is.** Confirm inserts the normal `budget_grants_expenditure` commitment row, with
  `source_module = procurement`, `source_reference` = the order id and `purchase_order_id` set, in the same transaction.
  That is the same row the `purchase-order.issued` consumer writes today, so the expenditure ledger, the existing
  payment and cancellation code, reports, reappropriation and grant closing all keep working unchanged.
- **Availability.** A line's available amount is its allocation, less committed and spent (the ledger, as today), less
  `reserved` rows of the commitments table. `committed` rows aren't counted twice: they already have their ledger row.

## Lifecycle

```
  reserve (order approval)                  confirm (order issued)
  ───────────────────────► reserved ───────────────────────────────► committed ──► ledger: commitment row
                              │                                         │          then, synchronously:
                              │ release (order returned, or a           │          cancel / close → release remainder
                              ▼ draft or returned order cancelled)      │          invoice paid  → commitment to spend
                           released (final; a new reservation is a new row)
```

| Event in procurement | Call to budget-grants (synchronous, idempotent) | Same key as the existing event consumer |
|---|---|---|
| Order approval starts | `POST /commitments` (reserve) | live row per order id |
| Order issued | `POST /commitments/procurement/{po}/confirm` → ledger commitment row | `(procurement, {po}, commitment)` |
| Order returned; draft or returned order cancelled | `POST /commitments/procurement/{po}/release` | live row per order id |
| Issued order cancelled, or its remainder closed | `POST /commitments/procurement/{po}/cancel` `{released_amount, reason}` → negative commitment, never more than the order still holds | `(procurement, {po}/cancelled, commitment)` |
| Vendor invoice paid | `POST /commitments/procurement/{po}/spend` `{vendor_invoice_id, amount, paid_on}` → release + actual | `(procurement, {vendor_invoice_id}, actual)` |

The last two calls do exactly what the `purchase-order.cancelled` and `vendor-invoice.paid` consumers do today, under
the same keys. So when the relay later delivers those events, they find the work done and record nothing. **The relay
becomes optional for procurement's money:** grant closing and reports are right without it.

**When a call fails** (budget-grants unreachable, which procurement shows as 503 `budget_check_unavailable`):
- *Reserve:* the approval is refused and the order stays `submitted`; nothing was held.
- *Confirm, after the order is issued:* the reservation stays `reserved`, which already counts in full, so nothing is
  under-counted. procurement marks the order `budget_synced = false` and retries.
- *Release:* the money stays held, which is the safe side. procurement marks the order `budget_synced = false` and
  retries.
- *Cancel or spend:* the procurement action is recorded anyway, because the cancellation or payment really happened.
  procurement marks the order `budget_synced = false` and retries.
- *Where retries happen:* at the start of every later approval on the same line, and on every later write to the
  order. Once the relay exists, its events also deliver the change, idempotently.
- *Visibility:* the Finance Staff widget shows how many orders are waiting to sync.

## Recovery of pending reservations

A live reservation always names its order (`source_reference` and `purchase_order_id`). That order is `submitted`
until someone decides it, so recovery is always "decide the order", and every call is idempotent.

| Situation | How it is noticed | How it recovers | Money meanwhile |
|---|---|---|---|
| procurement fails after reserving, before committing the issue | order still `submitted`; `GET /commitments?state=reserved` lists it | approving again reuses the live reservation (200), issues and confirms; returning releases it | held |
| confirm fails after the order is issued | order `budget_synced = false` | retried as above; the issued event confirms too once a relay exists | held in full (`reserved`) |
| release, cancel or spend fails | order `budget_synced = false` | retried as above | held (the safe side) |
| an order nobody decides | Finance Staff widget (awaiting approval); `GET /commitments?state=reserved&older_than_days=N` (uses `reserved_at`) | the approver decides it | held |
| an edited order (only possible after a return, which released it) | — | the next approval reserves a new row at the new total | — |
| a grant closed, or money reappropriated away from the line | — | a reservation counts as committed: closing is refused with `open_commitments`, and a reappropriation checks what is available after reservations | held |

There is **no manual release in budget-grants**: releasing a reservation whose order may still be issued would reopen
the overspend. A release only ever comes from procurement deciding the order.

## Contract (budget-grants, additive)

```yaml
/commitments:
  post:   # reserve
    summary: >-
      Reserve an amount on a budget or grant line for a procurement purchase order. Locks the line, checks the amount
      against what is available (allocated less committed, reserved and spent) and inserts a reserved row.
      Permission budget-grants:commitment:record.
    requestBody: CommitmentInput
    responses:
      "201": reserved now (Commitment)
      "200": the order already has a live row with the same line and amount (Commitment)
      "404": no such line in an approved budget or active grant of the caller's organisation
      "409": commitment_mismatch: the order's live row has a different line or amount
      "422": exceeds_available: the line cannot cover the amount; nothing is recorded
  get:    # list
    summary: >-
      Commitments, newest first. Filters: state, line_id, source_module, older_than_days (on reserved_at); cursor and
      limit. Permission budget-grants:budget:read.
    responses: { "200": CommitmentPage }
/commitments/{source_module}/{source_reference}/confirm:
  post: { summary: "reserved → committed, and the ledger commitment row; committed → 200 unchanged",
          responses: { "200": Commitment, "404": no live row, "409": released } }
/commitments/{source_module}/{source_reference}/release:
  post: { summary: "reserved → released; no live row → 200 (nothing to release); committed → 409 (use cancel)",
          requestBody: { reason }, responses: { "200": Commitment, "409": committed } }
/commitments/{source_module}/{source_reference}/cancel:
  post: { summary: "an issued order cancelled or closed: release released_amount (at most what the order still holds)",
          requestBody: { released_amount, reason }, responses: { "200": released amount, "404": no committed row } }
/commitments/{source_module}/{source_reference}/spend:
  post: { summary: "an invoice of the order paid: commitment to actual spend, as the vendor-invoice.paid consumer does",
          requestBody: { vendor_invoice_id, amount, paid_on }, responses: { "200": spend recorded, "404": no committed row } }

CommitmentInput: { line_id: uuid, amount: Money (> 0), source_module: enum [procurement], source_reference: string,
                   purchase_order_id: uuid, description: string }
Commitment: { id, organisation_id, line_id, amount, state: enum [reserved, committed, released], source: { module,
              reference }, purchase_order_id, reserved_at, reserved_by, confirmed_at?, released_at?, release_reason? }
```

**Event consumer changes** (they stay correct whether or not the synchronous calls already ran):
- `purchase-order.issued`:
  - a live `reserved` row is confirmed;
  - a live `committed` row means nothing to do;
  - if the order has no live row (it was issued before this change, or its only rows are released), it records a
    commitment as today.
- `purchase-order.cancelled` and `vendor-invoice.paid`: unchanged. Their keys are the ones the synchronous calls use, so
  a repeat records nothing.

**Audit:** every reserve, confirm, release, cancel and spend writes `budget_grants_audit_entry`, with the actor.

## Permissions

- New key **`budget-grants:commitment:record`**: "Reserve, confirm, release, cancel and spend commitments for documents
  of another module (procurement purchase orders)."
- Granted to **`management`** only, the role that holds `procurement:purchase-order:approve`, which approves, returns
  and cancels orders.
- Invoice payment is done by finance staff (`procurement:vendor-invoice:pay`), so `spend` is also granted to
  `finance-staff` under a separate key, **`budget-grants:commitment:spend`**. That keeps reserve and release with the
  approving role.

| Operation | Permission | Other checks |
|---|---|---|
| reserve | `commitment:record` | line open and in the caller's organisation (404); amount > 0 and at most what is available (422); live row with a different line or amount (409) |
| confirm, release, cancel | `commitment:record` | the row is in the caller's organisation (404); state rules as above (409) |
| spend | `commitment:spend` | a committed row for the order in the caller's organisation (404) |
| list | `budget:read` | the caller's organisation only |
| event consumers | none (the relay runs them in the event's organisation) | idempotent on the keys above |

Every lookup is scoped to the caller's organisation, so another organisation's row is a 404, never a 403.

## The trust boundary (decision 4)

budget-grants does not inspect procurement's order. Anyone holding `commitment:record` can call the API directly. In
practice that is every management user, because the permission belongs to a role, not to the procurement service. So a
management user could, outside procurement:
- release an issued order's reservation;
- reserve against a reference that matches no order, which holds money and blocks closing the grant.

**Mitigations in this design:**
- only one role holds the permission;
- every call is audited with its actor;
- stale reservations are listed (`older_than_days`);
- release is refused once committed.

**Two options for the decision:**
- **(a) Accept the risk** for v1 on these mitigations, and record it in the module README.
- **(b) Use a non-person service identity** for procurement's calls (Faizan, platform identity), so that no user holds
  `commitment:*` at all.

Recommendation: (a) for v1, (b) when identity supports service identities.

## Tests that must pass before risk 1 is closed

1. **budget-grants on Postgres:** a reserve racing a manual spend on one line. Exactly one succeeds when the line covers
   only one, and committed + reserved + spent never exceeds the allocation.
2. **budget-grants, idempotency:**
   - reserve, confirm, release, cancel and spend each called twice;
   - a mismatch is 409, and release of a committed row is 409;
   - a re-reservation after a release inserts a new row, and the released row is unchanged.
3. **budget-grants, reserve then confirm then invoice paid:** the paid invoice releases the commitment, found through
   `purchase_order_id`, and records the spend once, whether it comes from the synchronous call, the event, or both.
4. **budget-grants, the issued event:** it confirms a reserved row; it does nothing after a confirm; and with no live row
   it still records a commitment.
5. **procurement + budget-grants on Postgres** (`tests/integration/`): the reproduction above, an order against a manual
   spend with late and instant delivery, ends with the allocation never exceeded. Grant closing works after a
   cancellation without any relay.
6. **procurement, failures:**
   - a failure after reserving leaves the order `submitted` with the money reserved;
   - a failed confirm, release, cancel or spend sets `budget_synced = false` and is retried.
7. **Migration `budget_grants_0002`:** upgrade and downgrade; forced RLS on the new table; the partial unique index.

## Decisions needed

| # | Decision | Who | Status |
|---|---|---|---|
| 1 | Atomic reservation, confirmation on issue, release on return or cancellation; no expiry | Gokula (owner) | approved 29 Oct |
| 2 | v2: every procurement money change synchronous and keyed like the events; append-only commitments table | Gokula (owner) | proposed here |
| 3 | Permissions `commitment:record` for `management` and `commitment:spend` for `finance-staff` | Gokula (owner) | proposed here |
| 4 | Trust boundary: accept for v1 (a), or a service identity (b) | Gokula (owner), with Faizan for (b) | proposed: (a) |
| 5 | The cross-module contract and the `budget_grants_0002` migration | Faizan (architecture review) | to review |

## Delivery

| Step | What | Depends on |
|---|---|---|
| 1 | Contract PR (budget-grants): the endpoints, schemas, both permissions | decisions 2–5 |
| 2 | budget-grants backend: migration 0002, endpoints, consumer change, tests 1–4 and 7 | step 1 |
| 3 | procurement: approval, return, cancel and payment use the calls; `budget_synced` and retries; tests 5 and 6; the per-line advisory lock and the "not recorded yet" listing are removed | step 2, and #295 merged |

Until step 3 is merged and its tests pass, risk 1 in #295 stays **open**.
