# budget-grants: atomic commitments for procurement (proposal, v4)

Status: **design approved in direction by the module owner (29 Oct), not implemented.** Issue: #335 (was #129;
risk 1 in #295). Owner: Gokula Lakshmi (budget-grants and procurement). Reviewer: Ashritha. Architecture review:
Faizan (cross-module contract and migration). The overspend risk stays **open** until the delivery below is merged
and its concurrency tests pass.

**v2** answered the review on #350:
- procurement's money changes became synchronous;
- reservations record `purchase_order_id`;
- reservations got their own append-only table;
- the trust boundary became a recorded decision.

**v3** fixes what an independent check of v2 against the code found:
- the functions that must count reservations are now listed (v2 wrongly said they stay unchanged);
- the trust boundary names the real risks;
- spend is capped;
- retries run with a token that holds the right permission;
- cancel and spend confirm first;
- grant close and revision take the line lock;
- recovery of orphan reservations is defined;
- the gaps in the input and the tests are closed.

**v4** answers the review of v3 on #350:
- spend is capped on what the order **still holds** (its outstanding commitment), not on what was committed, so money
  a cancel or close released can't be counted twice;
- the spend call runs inside `mark-paid`, before procurement records the payment: a refusal leaves the invoice
  approved, with nothing pending and no event published (decision 5);
- the trust boundary adds that management can release a still-reserved row of an issued order, and confirm says what
  it does when only released rows exist.

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

In procurement, approval and issue are one step (`decide_order` issues the order it approves). So `reserved` is normally
transient: it lasts only while the approval request runs, unless a call fails.

## Storage: an append-only commitments table

A new table `budget_grants_commitment`. Like every table, it has `organisation_id` and the forced `tenant_isolation`
row-level-security policy. Migration `budget_grants_0002` creates it.

| Column | Type | Notes |
|---|---|---|
| `id`, `organisation_id` | String(36) | |
| `line_id` | String(36), FK line | |
| `source_module`, `source_reference` | String(30), String(120) | `procurement` and the purchase order id |
| `purchase_order_id` | String(36), indexed | always equal to `source_reference` for procurement (set by budget-grants, not sent by the caller); how the payment and cancellation code finds an order's commitment |
| `amount` | Numeric(14, 2) | the reserved order total |
| `state` | String(10) | `reserved`, `committed`, `released` |
| `reserved_at`, `reserved_by` | DateTime, String(36) | |
| `confirmed_at`, `confirmed_by` | DateTime, String(36), nullable | |
| `released_at`, `released_by`, `release_reason` | DateTime, String(36), Text, nullable | |

- **Append-only lifecycle.** A row moves `reserved → committed` or `reserved → released`, and never back.
  - A released row is never reactivated.
  - Reserving the same order again, after a return, inserts a **new** row.
  - Amount, line and source never change after insert.
  - A `committed` row stays `committed` after the order is fully paid or cancelled: what is outstanding lives in the
    ledger. The list endpoint therefore returns a derived `outstanding` amount, taken from the ledger, next to `state`.
- **Idempotency key.** At most one *live* row (`reserved` or `committed`) per `(organisation_id, source_module,
  source_reference)`. It is enforced by a partial unique index (`Index(..., unique=True, postgresql_where=...,
  sqlite_where=...)`, as fees-accounts already does in its model and migration). Released rows don't count towards the
  key. A concurrent duplicate that hits the index or the ledger's unique key answers 200 with the existing row, as
  `consumers.handle` maps `IntegrityError`.
- **The ledger is unchanged in shape.** Confirm inserts the normal `budget_grants_expenditure` commitment row, with
  `source_module = procurement`, `source_reference` = the order id and `purchase_order_id` set, in the same
  transaction that marks the row `committed`. That is exactly the row the `purchase-order.issued` consumer writes today.

### Which existing functions change: reservations must count everywhere money is read

Reservations are **not** ledger rows, so every function that reads a line's totals must add them. One helper,
`line_reserved(db, line_ids)`, sums the live `reserved` rows. `line_totals` returns (committed + reserved, spent), so
every caller sees reservations without a second code path. The callers, in `application/service.py` on `main`:

| Function | Today | With reservations |
|---|---|---|
| `line_available` (availability, manual spend, reappropriation request and decision, procurement's check) | allocated − committed − spent from the ledger | also less reserved |
| `close_grant` (`open_commitments`) | refuses while the ledger commitment total > 0 | also refuses while anything is reserved |
| `update_grant` (`below_used`) | a line can't drop below committed + spent | ... + reserved |
| `check_thresholds` | 80% and 100% alerts on committed + spent | ... + reserved |
| `line_dicts`, `grant_dict`, `list_lines`, `reports.budget_vs_spend` | show committed and spent | committed includes reserved; the line also shows `reserved` on its own |

A row moving `reserved → committed` stops counting as reserved in the same transaction that inserts its ledger
commitment, so it is never counted twice and never missed.

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
| Order approved and issued | `POST /commitments` (reserve), then `POST /commitments/procurement/{po}/confirm` → ledger commitment row | `(procurement, {po}, commitment)` |
| Order returned; draft or returned order cancelled | `POST /commitments/procurement/{po}/release` | live row per order id |
| Issued order cancelled, or its remainder closed | `POST /commitments/procurement/{po}/cancel` `{released_amount, reason}` → negative commitment, never more than the order still holds | `(procurement, {po}/cancelled, commitment)` |
| Vendor invoice paid | `POST /commitments/procurement/{po}/spend` `{vendor_invoice_id, amount, paid_on}` → release + actual | `(procurement, {vendor_invoice_id}, actual)` |

- **Confirm first.** `cancel` and `spend` first confirm a `reserved` row in the same transaction. So if confirm failed
  earlier, a later cancellation or payment still lands, and never answers 404.
- **Orders issued before this change** have no commitments row, only a ledger commitment. `cancel` and `spend` fall back
  to the ledger by `purchase_order_id`, exactly as the consumers do. Migration 0002 also backfills a `committed` row for
  every procurement ledger commitment that has no release.

The cancel and spend calls do exactly what the `purchase-order.cancelled` and `vendor-invoice.paid` consumers do today,
under the same keys. So when the relay later delivers those events, they find the work done and record nothing.
**The relay becomes optional for procurement's money.**

### Spend is capped (it can't be a back door)

`spend` releases `min(amount, outstanding commitment)` and records `amount` as actual spend, as the consumer does. On
its own that would let a caller record unlimited actual spend with any invoice id. So, under the line lock:
- **The order's outstanding commitment** is what the ledger still holds for it at the moment of the call: committed,
  less what `cancel` released, less what earlier payments already turned into spend. Only that part of the amount is
  accepted without a further check; it was checked when it was reserved and nobody else can use it.
- **Any excess** over the outstanding commitment is new money on the line. It is checked against the line's
  availability, like manual spend. If the line can't cover it, the call answers 422 `exceeds_available` and records
  nothing. This covers an invoice above the order (which procurement allows only with an approver's override note) and,
  as importantly, an order whose remainder was cancelled or closed: the released money went back to the line and may
  already be spent.
- **`vendor_invoice_id` must be a real invoice.** budget-grants can't check that across modules, so the cap above is
  what bounds it. procurement sends only its own invoices.

The reviewer's case on a ₹2,000 line, which must be a test (test 3):

| Step | Effect | Available |
|---|---|---|
| Order of ₹1,180 confirmed | committed ₹1,180 | ₹820 |
| ₹500 delivered, the rest closed | `cancel` releases ₹680; outstanding ₹500 | ₹1,500 |
| Manual spend of ₹1,500 | spent ₹1,500 | ₹0 |
| Invoice of ₹1,180 (override) paid | ₹500 from the commitment, ₹680 excess checked: **422 `exceeds_available`**, nothing recorded | ₹0 |

Capping on the committed amount (v3) would have accepted the ₹680 and left the line ₹680 over its allocation.

**When spend answers 422 (decision 5).** The call is made inside procurement's `mark-paid`, before procurement records
the payment, as reserve is made inside approval:
- a 422 `exceeds_available` refuses `mark-paid` (422 `insufficient_budget`, with the uncovered amount). The invoice stays
  `approved`, nothing is recorded in either module, nothing is pending, and no `vendor-invoice.paid` event is
  published, so the consumer never records it unchecked;
- finance staff free money for the line first (a reappropriation, decided by management) and mark it paid again. Payment
  at the bank follows `mark-paid` in Education OS, as for every other payment the module records;
- budget-grants unreachable (503) or a timeout also refuses `mark-paid` and leaves the invoice `approved`. If
  budget-grants did record it, the retry finds the same key and answers 200: the spend is recorded once.

So `spend` is never left pending. *Proposed rule; the module owner decides: refuse the uncovered excess as above, or
record it and raise the 100% threshold alert.*

### When a call fails

budget-grants unreachable shows in procurement as 503 `budget_check_unavailable`. A 403 means the role setup is wrong and
shows as 503 `budget_permission_missing`.
- *Reserve:* the approval is refused and the order stays `submitted`. If the request timed out after budget-grants
  recorded it, the reservation is held, and the next approval reuses it (200).
- *Spend:* never pending. It runs inside `mark-paid`, and any failure refuses `mark-paid` (above).
- *Confirm, release or cancel:* procurement records which operation is pending on the order (`budget_pending`: a list
  such as `confirm`, `release`, `cancel`), not a single flag. It retries them in lifecycle order: confirm, then cancel.
- *Who retries, so the token has the permission:*
  - **management** actions (any approval, return or cancel in the organisation) retry pending confirm, release and
    cancel;
  - a **"Sync now"** action, for management, does the same.
  - Writes by other roles (receipts, edits, payments) don't retry, because they don't hold `commitment:record`.
- **An approval retries a pending release before it reserves again.** A 409 `commitment_mismatch` triggers that release,
  then the reservation.
- **Money always errs on the held side:** a pending confirm stays `reserved`, which is counted; a pending release keeps
  money held. Once the relay exists, its events also deliver a pending cancel, idempotently.

## Recovery of pending reservations

| Situation | How it is noticed | How it recovers | Money meanwhile |
|---|---|---|---|
| procurement fails after reserving, before committing the issue | order still `submitted`; `GET /commitments?state=reserved` lists it | approving again reuses the live reservation (200), issues and confirms; returning releases it | held |
| confirm, release or cancel fails | order `budget_pending` | retried by management (above), or "Sync now"; cancel and spend confirm first | held (the safe side) |
| spend fails or is refused | `mark-paid` answers 422 or 503; the invoice stays `approved` | finance staff mark it paid again once the line is covered or budget-grants is back | held as commitment; nothing paid is recorded |
| a reserved row of an issued order was released (by a direct call) before its confirm | confirm finds only released rows | confirm re-reserves under the line lock (below), or 422 and the order stays `budget_pending` | held if the line covers it; otherwise shown to management |
| an order nobody decides | Finance Staff widget (awaiting approval); `GET /commitments?state=reserved&older_than_days=N` (uses `reserved_at`) | the approver decides it | held |
| an edited order after a failed release | approval finds `release` pending, or gets 409 `commitment_mismatch` | approval releases, then reserves the new total as a new row | held until then |
| an **orphan reservation** (no order behind it, e.g. one reserved by a direct call) | `GET /commitments?state=reserved&older_than_days=N` | a management user calls `release` with a reason, audited | held until released |
| a grant closed, or money reappropriated away | — | `close_grant` refuses while anything is reserved or committed; reappropriation checks availability after reservations | held |

Releasing is limited to `commitment:record` holders, who are management, and every release is audited. There is no
other way to release a reservation.

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
      Commitments, newest first, each with its derived outstanding amount. Filters: state, line_id, source_module,
      older_than_days (on reserved_at); cursor and limit. Permission budget-grants:budget:read.
    responses: { "200": CommitmentPage }
/commitments/{source_module}/{source_reference}/confirm:
  post: { summary: "reserved → committed, with its ledger commitment row; committed → 200 unchanged; only released rows → a new reservation of the last released amount and line, availability checked under the line lock, then committed (audited as recommitted)",
          responses: { "200": Commitment, "404": "no row at all in the caller's organisation", "422": "exceeds_available: only released rows, and the line can no longer cover the order" } }
/commitments/{source_module}/{source_reference}/release:
  post: { summary: "reserved → released; no live row → 200, nothing to release (another organisation's row looks the same); committed → 409, use cancel",
          requestBody: { reason }, responses: { "200": Commitment or nothing, "409": committed } }
/commitments/{source_module}/{source_reference}/cancel:
  post: { summary: "issued order cancelled or closed: confirm a reserved row first, then release released_amount (at most what the order still holds)",
          requestBody: { released_amount, reason }, responses: { "200": released amount, "404": no row and no ledger commitment } }
/commitments/{source_module}/{source_reference}/spend:
  post: { summary: "invoice of the order paid (called inside mark-paid): confirm a reserved row first, then commitment to actual; only the order's outstanding commitment is accepted unchecked, any excess is checked against availability; Permission budget-grants:commitment:spend",
          requestBody: { vendor_invoice_id, amount, paid_on },
          responses: { "200": spend recorded, "404": no row and no ledger commitment, "422": exceeds_available for an uncovered excess } }

CommitmentInput: { line_id: uuid, amount: Money (> 0), source_module: enum [procurement], source_reference: string,
                   description: string }        # purchase_order_id is set to source_reference by budget-grants
Commitment: { id, organisation_id, line_id, amount, state: enum [reserved, committed, released], source: { module,
              reference }, purchase_order_id, outstanding, reserved_at, reserved_by, confirmed_at?, released_at?,
              release_reason? }
```

**Event consumer changes.** They stay correct whether or not the synchronous calls already ran.
- **`purchase-order.issued`:**
  1. It keeps its existing first check, `_exists(procurement, po, commitment)`. A ledger row means nothing to do.
  2. Otherwise, a live `reserved` row is confirmed.
  3. With no row at all (orders issued before this change), it records a commitment as today.
  4. With only released rows, it does what confirm does: re-reserve under the line lock and commit. An event can't be
     refused, so if the line no longer covers the order the commitment is still recorded (the order was issued) and the
     100% threshold alert fires. procurement's own confirm normally gets there first and answers 422 instead.
- **`purchase-order.cancelled` and `vendor-invoice.paid`:** unchanged. Their keys are the ones the synchronous calls
  use, so a repeat records nothing.

**Audit:** every reserve, confirm, release, cancel and spend writes `budget_grants_audit_entry`, with the actor.

## Permissions

- **`budget-grants:commitment:record`** ("Reserve, confirm, release and cancel commitments for procurement purchase
  orders") goes to **`management`** only. That is the role holding `procurement:purchase-order:approve`, which covers
  approve, return and cancel, including cancelling a draft or returned order. So it covers every procurement call made
  with a management token.
- **`budget-grants:commitment:spend`** ("Record the payment of a procurement purchase order's invoice against its
  commitment") goes to **`finance-staff`** only. That is the role holding `procurement:vendor-invoice:pay`, the only
  role that marks invoices paid; management holds `vendor-invoice:approve`, not pay.
- **Why spend is a separate key rather than reusing `budget-grants:expenditure:record`:**
  - finance staff already hold `expenditure:record`, but that right is bounded by availability and reversible
    (`reverse_expenditure`);
  - spend writes procurement-sourced entries that `reverse_expenditure` refuses to reverse;
  - so the two must not share a key.
- **Why spend can't be left to the event consumer:** nothing calls the consumer until the relay (#83) exists.

| Operation | Permission | Other checks |
|---|---|---|
| reserve | `commitment:record` | line open and in the caller's organisation (404); amount > 0 and at most what is available (422); live row with a different line or amount (409) |
| confirm, release, cancel | `commitment:record` | the row is in the caller's organisation (404, or 200 for release); state rules as above (409) |
| spend | `commitment:spend` | a committed row, or a ledger commitment for the order, in the caller's organisation (404); the cap above (422) |
| list | `budget:read` | the caller's organisation only |
| event consumers | none (the relay runs them in the event's organisation) | idempotent on the keys above |

Every lookup is scoped to the caller's organisation, so another organisation's row is a 404, or "nothing to release",
never a 403.

## Locking: every path that changes a line's money

| Path | Lock today | With this design |
|---|---|---|
| manual spend, the four event consumers, reappropriation decision | the line row (`FOR UPDATE`) | unchanged |
| reserve, confirm, release, cancel, spend | — | the line row (`FOR UPDATE`) |
| `update_grant` (lines revised, `below_used`) | the grant row only | also the grant's line rows, `FOR UPDATE`, before reading totals |
| `close_grant` | the grant row only | also the grant's line rows, `FOR UPDATE`, before reading totals, so a reserve and a close can't both succeed |
| reserve | — | reads the budget's or grant's status under the line lock, and re-checks it is open after locking |

Payroll locks the line but never checks availability: payroll is real spend and is always recorded. So "never exceeds
the allocation" in test 1 is about manual spend, as stated there.

## The trust boundary (decision 4)

budget-grants does not inspect procurement's order. The permissions belong to roles, not to the procurement service, so
these users can call the API directly, outside procurement:
- **any management user** (`commitment:record`) can **cancel an issued order's commitment**, up to what the order still
  holds. That releases money procurement still owes and reopens room for overspend. They can also reserve against a
  reference that matches no order (an orphan), which holds money.
- **any management user** can also **release a still-reserved row of an issued order** whose confirm is pending (a
  failed confirm leaves the row `reserved`). budget-grants can't tell that the order was issued, so the release
  succeeds and the money goes back to the line. The pending confirm then finds only released rows: it re-reserves the
  same amount on the same line under the line lock, checking availability, and commits it (audited as `recommitted`). If
  the line was spent meanwhile, confirm answers 422 `exceeds_available`; the order stays `budget_pending: confirm`
  and is shown to management, who free money for the line. Until then the issued order is not held on the line, which
  is the overspend window this risk names.
- **any finance-staff user** (`commitment:spend`) can turn an issued order's commitment into actual spend with invoice
  ids procurement doesn't have. That is bounded by the cap above, and the entries can't be reversed by
  `reverse_expenditure`.

**Real mitigations:**
- each permission is held by exactly one role;
- every call is audited with its actor;
- spend is capped on the order's outstanding commitment;
- orphan reservations are listed and released by management, audited;
- a confirm after such a release re-checks availability, so it never recommits money the line no longer has;
- release is never possible for a committed row (cancel is the path, and it is audited).

**Two options:**
- **(a) Accept these risks for v1** on the mitigations above, and record them in the module README.
- **(b) Use a non-person service identity** for procurement's calls (Faizan, platform identity), so that no user holds
  `commitment:*` at all. This removes both risks.

Recommendation: (a) for v1, (b) when identity supports service identities.

## Tests that must pass before risk 1 is closed

1. **budget-grants on Postgres:** a reserve racing a manual spend on one line. Exactly one succeeds when the line covers
   only one, and committed + reserved + spent never exceeds the allocation.
2. **budget-grants, idempotency:**
   - reserve, confirm, release, cancel and spend each called twice, including concurrent duplicates (200, not 500);
   - a mismatch is 409;
   - release of a committed row is 409;
   - a re-reservation after a release inserts a new row, and the released row is unchanged.
3. **budget-grants, the money path:** reserve, confirm, then invoice paid. The payment releases the commitment, found
   through `purchase_order_id`, and records the spend once, whether it comes from the synchronous call, the event, or
   both. Cancel and spend on a still-`reserved` row confirm first. Spend above the order's outstanding commitment is
   checked against availability, including the reviewer's case: ₹2,000 line, ₹1,180 order, ₹680 closed, ₹1,500 manual
   spend, then a ₹1,180 invoice paid → 422 and nothing recorded. A confirm that finds only released rows re-reserves
   when the line covers it and answers 422 when it doesn't.
4. **budget-grants, reservations count everywhere:**
   - availability, manual spend and reappropriation see a reservation;
   - `close_grant` refuses with a reservation;
   - `update_grant` can't drop a line below committed + reserved + spent;
   - thresholds fire on reserved amounts.
5. **budget-grants, the issued event:**
   - it does nothing when the ledger row exists;
   - it confirms a reserved row;
   - with no live row it still records a commitment.
6. **budget-grants, permissions and tenancy:**
   - finance-staff get 403 on reserve, confirm, release and cancel;
   - management get 403 on spend;
   - every commitments endpoint is cross-tenant (404, and "nothing to release");
   - the list is covered by the cross-tenant leak test.
7. **procurement + budget-grants on Postgres** (`tests/integration/`):
   - the reproduction above, an order against a manual spend with late and instant delivery, ends with the allocation
     never exceeded;
   - grant closing works after a cancellation without any relay;
   - a close racing a reserve can't both succeed.
8. **procurement, failures:**
   - a failure after reserving leaves the order `submitted` with the money reserved;
   - a failed confirm, release or cancel is recorded in `budget_pending` and retried by management, or by "Sync now";
   - a spend that answers 422 or 503 refuses `mark-paid`: the invoice stays `approved`, no `vendor-invoice.paid` event
     is published, and marking it paid again after a timeout records the spend once;
   - an edit after a failed release re-reserves correctly;
   - a 403 shows as `budget_permission_missing`.
9. **Migration `budget_grants_0002`:**
   - upgrade and downgrade;
   - forced RLS on the new table;
   - the partial unique index, which the drift test compares;
   - the backfill of existing procurement commitments.

## Decisions needed

| # | Decision | Who | Status |
|---|---|---|---|
| 1 | Atomic reservation, confirmation on issue, release on return or cancellation; no expiry | Gokula (owner) | approved 29 Oct |
| 2 | Every procurement money change synchronous and keyed like the events; append-only commitments table; reservations counted by `line_totals` everywhere | Gokula (owner) | proposed |
| 3 | `commitment:record` for `management` only; `commitment:spend` for `finance-staff` only | Gokula (owner) | proposed |
| 4 | Trust boundary: accept the named risks for v1 (a), or a service identity (b) | Gokula (owner), with Faizan for (b) | proposed: (a) |
| 5 | Spend above the order's outstanding commitment: refuse `mark-paid` when uncovered (422, invoice stays approved, nothing pending), or record and alert | Gokula (owner) | proposed: refuse |
| 6 | The cross-module contract, the `budget_grants_0002` migration with its backfill, and the grant locking changes | Faizan (architecture review) | to review |

## Delivery

| Step | What | Depends on |
|---|---|---|
| 1 | Contract PR (budget-grants): the endpoints, schemas, both permissions | decisions 2–6 |
| 2 | budget-grants backend: migration 0002 with backfill, `line_reserved` in `line_totals`, endpoints, consumer change, grant locking, tests 1–6 and 9 | step 1 |
| 3 | procurement: approval, return, cancel and payment use the calls; `budget_pending`, role-scoped retries and "Sync now"; tests 7 and 8; the per-line advisory lock and the "not recorded yet" listing are removed | step 2, and #295 merged |

Until step 3 is merged and its tests pass, risk 1 in #295 stays **open**.
