# budget-grants: atomic commitments for procurement (proposal)

Status: **design approved in direction by the module owner (29 Oct), not implemented.** Issue: #335 (was #129;
risk 1 in #295). Owner: Gokula Lakshmi (budget-grants and procurement). Reviewer: Ashritha. Architecture review:
Faizan (cross-module contract and migration). The overspend risk stays **open** until the delivery below is merged
and its concurrency tests pass.

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

procurement asks budget-grants to **reserve** the order total, and budget-grants checks and records the reservation in
one transaction, under the same line-row lock manual spend and payroll take. A reservation counts against the line from
that moment, whether or not the order is issued yet.

## Lifecycle (no relay, no scheduler)

```
            reserve (order approval)            confirm (order issued)
  (none) ───────────────────────────► reserved ──────────────────────────► committed ──► existing flows
                                          │                                            (cancel / close: release
                                          │ release (order returned or edited,           the remainder; invoice
                                          ▼  approval abandoned)                         paid: commitment → spend)
                                       released ── reserve again (same order) ──► reserved
```

| State | Counts against the line | Reached by | Left by |
|---|---|---|---|
| `reserved` | **yes**, from the moment it is recorded | `POST /commitments` | confirm, or release |
| `committed` | yes | confirm, or the `purchase-order.issued` event | the existing release (`purchase-order.cancelled`) and payment (`vendor-invoice.paid`) flows |
| `released` | no | release | reserve again for the same order |

There is no expiry. Every `reserved` entry belongs to one procurement order that is still `submitted`. Every way an
order leaves `submitted` confirms or releases its reservation, so nothing leaks and no sweep is needed:

| What happens in procurement | Call | Result in budget-grants |
|---|---|---|
| Approval starts | `POST /commitments` (reserve) | `reserved`, or 422 and nothing recorded |
| Approval commits the issued order | confirm | `committed` |
| procurement's own transaction fails after reserving (crash, error) | none (the order stays `submitted`) | stays `reserved`: the money stays held, the safe side. The next approval reuses it (idempotent) or a return releases it. |
| Confirm fails after the order is issued (budget-grants unreachable) | retried at the next approval on the line, and on any later write to the order; the issued event confirms too, once a relay exists | stays `reserved`, which already counts in full: nothing is under-counted |
| Order returned (or edited, which needs `returned`) | release | `released` |
| Order cancelled or closed after issue | none new: `purchase-order.cancelled` releases the undelivered remainder as today | unchanged |

What is safe without a relay: the money is always held from reservation on. The only thing a relay adds later is
confirming a reservation whose confirm call failed; until then it simply stays `reserved`, counted in full.

## Recovery of pending reservations

A reservation is never orphaned: it always names its purchase order (`source_reference`), and that order is
`submitted` until someone decides it. So recovery is always "decide the order", and every path below is idempotent.

| Situation | How it is noticed | How it recovers | Money in the meantime |
|---|---|---|---|
| procurement fails after reserving and before committing the issue (error, crash, timeout) | the order is still `submitted`; budget-grants lists the reservation (`GET /commitments?state=reserved`) | approving again reserves again, gets the existing reservation (200), issues and confirms; returning the order releases it | held: counted against the line |
| confirm fails after the order is issued (budget-grants unreachable) | procurement marks the order `commitment_confirmed = false` | confirm is retried at the start of every later approval on the same line and on every later write to the order (receipt, invoice, cancel); once the relay exists, the order's `purchase-order.issued` event confirms too | held in full as `reserved`: nothing is under-counted |
| an order is returned, or a draft or returned order is cancelled | procurement's own action | release (a 404 from budget-grants means nothing was reserved, which is fine) | freed |
| an order is edited (only possible when `draft` or `returned`, so already released) | — | the next approval reserves the new total and reactivates the same row | — |
| a `submitted` order nobody decides | the Finance Staff widget shows it as awaiting approval; `GET /commitments?state=reserved&older_than_days=N` shows how long the money has been held | the approver decides it (approve, or return) | held |
| a grant is closed, or a reappropriation moves money from the line | — | a reservation counts as a commitment: closing is refused with `open_commitments`, and a reappropriation checks what is available after reservations | held |

There is **no manual release in budget-grants**: releasing a reservation whose order may still be issued would reopen
the overspend. A release only ever comes from procurement deciding the order. An emergency override (for an order
that can no longer be decided) would be a separate, audited permission; it is not proposed here.

## Contract (budget-grants, additive)

```yaml
/commitments:
  post:
    summary: >-
      Reserve an amount on a budget or grant line for another module's document (a purchase order). Locks the line,
      checks the amount against what is available (allocated less committed, reserved and spent), and records a
      reserved commitment. Idempotent per source. Permission budget-grants:commitment:record.
    requestBody: CommitmentInput
    responses:
      "201": reserved now (Commitment)
      "200": the same source was already reserved or committed with the same line and amount (Commitment)
      "404": no such line in an approved budget or active grant
      "409": commitment_mismatch — the same source holds a different line or amount
      "422": exceeds_available — the line cannot cover the amount; nothing is recorded
/commitments/{source_module}/{source_reference}/confirm:
  post:
    summary: The document was issued. reserved → committed; committed → 200 unchanged. Permission commitment:record.
    responses: { "200": Commitment, "404": no such reservation, "409": released }
/commitments (list):
  get:
    summary: >-
      Reservations and commitments recorded through this API, newest first, for finding reservations held long.
      Filters: state, line_id, source_module, older_than_days; cursor and limit. Permission budget-grants:budget:read.
    responses: { "200": CommitmentPage }
/commitments/{source_module}/{source_reference}/release:
  post:
    summary: >-
      The document will not be issued. reserved → released; released → 200 unchanged. A committed entry is not
      released here (the document's own cancellation event does that). Permission commitment:record.
    requestBody: { reason: string }
    responses: { "200": Commitment, "404": no such reservation, "409": committed }

CommitmentInput: { line_id: uuid, amount: Money (> 0), source_module: enum [procurement], source_reference: string,
                   description: string }
Commitment: { id, organisation_id, line_id, amount, state: enum [reserved, committed, released],
              source: { module, reference }, reserved_at, confirmed_at?, released_at?, release_reason? }
```

- **Idempotency key:** `(organisation_id, source_module, source_reference, kind = commitment)`. This is the unique key
  the `purchase-order.issued` consumer already uses, with `source_reference` = the purchase order id, so a reservation,
  its confirm and the later event can never record the order twice.
- **Storage:** the existing `budget_grants_expenditure` row of kind `commitment`, plus a `state` column (`reserved` or
  `committed`; migration `budget_grants_0002`, default `committed` for existing rows). Release sets `reversed = true`
  with the reason, as entries are never deleted. Reserving the same order again reactivates its row. Totals already
  count unreversed commitments, so a reservation counts at once and a release stops counting.
- **Event consumer change:** `procurement.purchase-order.issued` confirms a `reserved` entry with its key, ignores a
  `committed` one, and records a commitment as today when none exists (orders approved before the change).
- **Audit:** every reserve, confirm and release writes `budget_grants_audit_entry`.

## Permission (least privilege)

- New key **`budget-grants:commitment:record`**: "Reserve, confirm and release commitments for documents of another
  module (procurement purchase orders)."
- Granted initially to **`management`** only: the role that holds `procurement:purchase-order:approve`, so only the
  order approval workflow uses it. Not to finance staff, so preparing an order never touches the budget.
- With it, procurement's order approval no longer needs `GET /availability` or `GET /expenditures`
  (`budget-grants:budget:read`). Indent approval still uses `GET /availability`.

## Permission checks per operation

| Operation | Permission | Other checks | Called by |
|---|---|---|---|
| `POST /commitments` (reserve) | `budget-grants:commitment:record` | the line is open and in the caller's organisation (404); `source_module` is a known module (422); the amount is positive and at most what is available (422); the same source with a different line or amount (409) | procurement order approval, with the approver's token |
| `POST .../confirm` | `budget-grants:commitment:record` | the reservation exists in the caller's organisation (404); a released one (409) | procurement after issuing, and its retries |
| `POST .../release` | `budget-grants:commitment:record` | the reservation exists in the caller's organisation (404); a committed one (409, its cancellation event releases it) | procurement on returning an order, or cancelling a draft or returned one |
| `GET /commitments` | `budget-grants:budget:read` | the caller's organisation only | finance staff, management |
| `purchase-order.issued` consumer | none (the relay runs it in the event's organisation) | idempotent on the source key | the relay, once it exists |

- **Tenant isolation:** every lookup is scoped to the caller's organisation and every table keeps `organisation_id`
  with row-level security, so a reservation of another organisation is a 404, never a 403.
- **Trust boundary:** budget-grants does not inspect procurement's order. It trusts the permission, held only by the
  approving role, and records the actor on every reserve, confirm and release in its audit trail. Separation of
  duties (the preparer never approves) stays in procurement, which checks it before calling.
- **Who holds it:** the people who approve, return and cancel orders in procurement are the same role
  (`procurement:purchase-order:approve`, today `management`), so every procurement call that needs it is made with a
  token that has it. A role that approves orders without it gets 403 from budget-grants, which procurement shows as
  503 `budget_check_unavailable` and decides nothing.

## procurement changes (after budget-grants ships this)

- Order approval: lock the order → reserve (422 `insufficient_budget` and 503 `budget_check_unavailable` as today) →
  issue and commit → confirm. Confirm failures are recorded on the order and retried as above.
- Return of an order, and cancelling a draft or returned one: release (404 from budget-grants is fine: nothing was
  reserved).
- A `commitment_confirmed` flag on the order, set by confirm and retried while false (see recovery).
- Remove the per-line advisory lock and the "orders not recorded yet" listing: budget-grants' line lock replaces both.

## Tests that must pass before risk 1 is closed

1. budget-grants, Postgres: reserve racing a manual spend on one line. Exactly one succeeds when the line covers only
   one, and committed + reserved + spent never exceeds the allocation.
2. budget-grants: idempotency (reserve twice, confirm twice, release twice); mismatch is 409; release of committed is
   409; the issued event after confirm records nothing; the issued event without a reservation still commits.
3. procurement + budget-grants, Postgres (`tests/integration/`): the reproduction above (order against manual spend,
   late and instant delivery) ends with the allocation never exceeded.
4. procurement: a failure after reserve leaves the order `submitted` and the money reserved; approving again reuses the
   reservation; returning releases it.
5. Migration `budget_grants_0002`: upgrade, downgrade, existing commitments read as `committed`.

## Decisions needed

| # | Decision | Who | Status |
|---|---|---|---|
| 1 | Atomic reservation, confirmation on issue, release on return or cancellation; no expiry | Gokula (owner) | approved 29 Oct |
| 2 | Recovery as above, with no manual release in budget-grants | Gokula (owner) | proposed here |
| 3 | Permission `budget-grants:commitment:record`, granted to `management` only, checked as above | Gokula (owner) | proposed here |
| 4 | The cross-module contract and the `budget_grants_0002` migration | Faizan (architecture review) | to review |

## Delivery

| Step | What | Depends on |
|---|---|---|
| 1 | Contract PR (budget-grants): the endpoints, schemas, permission | decisions 1–4 |
| 2 | budget-grants backend: migration 0002, endpoints, consumer change, tests 1, 2, 5 | step 1 |
| 3 | procurement: approval and return use the commitments; tests 3, 4; remove the advisory lock and listing | step 2, and #295 merged |

Until step 3 is merged and its tests pass, risk 1 in #295 stays **open**.
