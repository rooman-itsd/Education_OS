# procurement

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend and widget built; enabled in `apps/backend` and `apps/frontend`)

Buying goods and services from request to payment: vendors, indents (purchase requests), quotation requests and
tenders, purchase orders, goods receipts and vendor invoices. Every purchase is charged to a budget or grant line in
budget-grants. Requirements: [docs/prd.md](docs/prd.md); stories: [docs/user-stories.md](docs/user-stories.md).

## Scope
- **In scope:** vendors and their approval; indents charged to a budget or grant line; quotation requests and tenders
  with the comparative statement and award; purchase orders with approval; goods receipts; vendor invoices matched
  against the order and receipts, approved and recorded as paid.
- **Not in scope:**
  - stock and asset registers (facilities modules react to `procurement.goods-receipt.recorded`);
  - making the bank payment itself (the payment is recorded after it is made);
  - budgets and spend (budget-grants);
  - government e-procurement portals.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/procurement`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_procurement/domain/rules.py` | Exact money and quantities, the purchase method by value, order totals, invoice matching, the masked bank account. Pure Python. |
| application | `application/service.py` | Vendors (register, edit, approve, suspend, blacklist); indents (raise, edit, submit, decide with the budget check); quotation requests and tenders (create, publish, record quotes, award); purchase orders (direct or from an award, edit, submit, approve or return, cancel); goods receipts; vendor invoices (record, match, approve or reject, mark paid). |
| | `application/reports.py` | Orders awaiting approval and delivery, overdue deliveries and invoices awaiting payment. |
| infrastructure | `infrastructure/models.py` | 10 `procurement_*` tables, including `audit_entry`. Each has `organisation_id`; money is `Numeric(14, 2)`. |
| | `infrastructure/budget_grants.py` | HTTP client for budget-grants `GET /availability`. It forwards the caller's token. |
| | `infrastructure/config.py` | `PROCUREMENT_*` settings. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `procurement_0001` with its own version table. It applies the `tenant_isolation` policy on Postgres. |

Rules the code keeps:
- **Preparer and approver are different people.** The requester never decides an indent. Whoever last edited or
  submitted an order prepared it and can't approve it. Whoever recorded an invoice can't approve it.
- **Approval checks the budget.** Approving an indent calls budget-grants `GET /availability` for the estimated cost,
  with the approver's token. A line that can't cover it, or isn't open, is 422 `insufficient_budget`. If budget-grants
  can't be reached, refuses the check or gives an unreadable answer, the answer is 503 `budget_check_unavailable` and
  nothing is decided. Nothing is reserved: the commitment starts when the order is issued (#221).
- **An order is issued only if its line covers its total** (decided by the owner; see #335). Approving a purchase order asks
  budget-grants `GET /availability` for the order total and `GET /expenditures` (commitments) for the line, with the
  approver's token, so the approver needs `budget-grants:availability:read` and `budget-grants:budget:read`.
  budget-grants records a commitment only when `procurement.purchase-order.issued` reaches it, so the totals of this
  organisation's issued orders on the line that budget-grants has not recorded yet are taken off what it reports.
  Approvals on one line are serialised by a Postgres transaction-level advisory lock, so two approvals cannot spend
  the same balance. A line that can't cover the total is 422 `insufficient_budget`; budget-grants unreachable or
  refusing is 503 `budget_check_unavailable`. Either way the order stays submitted and nothing is published.
- **The purchase method follows the value.** Up to `PROCUREMENT_DIRECT_PURCHASE_LIMIT` a direct purchase, up to
  `PROCUREMENT_QUOTATION_LIMIT` quotations, above it a tender. The limits have no default: until both are set, approval
  is 422 `purchase_limits_not_configured` (decided by the owner; see #335). A tender may use a stricter method than its indents need,
  never a looser one, judged on their combined value too. Only direct-purchase indents become an order directly, and
  only while their combined estimate and the order's own total stay within the direct limit (422 `tender_required`), so
  a purchase can't be split into direct orders or priced above what was approved.
- **An indent belongs to one open tender or order at a time.** Indents combined into one tender or order share one line.
  The indents are locked while checked, so two requests for the same indent take turns. When an order is cancelled
  with nothing received, its indents can be ordered again. A tender that can no longer be awarded lets its indents
  go: a draft past its closing date, or a closed tender none of whose quotes can be awarded (each expired, unpriced or
  from a vendor no longer approved); the contract has no way to cancel a tender. A suspension can be lifted, so such a
  tender may become awardable again: its award locks and checks its indents first, and answers 409 `indent_in_use`
  when another tender or order took them meanwhile.
- **An order that was never issued can be cancelled.** A draft or returned order is cancelled with a reason, without an
  event (nothing was committed), and its indents can be ordered again; a submitted order is decided first (409
  `not_cancellable` otherwise).
- **Order dates follow the order.** `delivery_by` can't be before today (on create, edit and submit, so a draft left
  past its date is corrected before it goes out), and `received_on` can't be before the order was issued or after
  today (422 `invalid_date`).
- **Blacklisting is final** (409 `vendor_blacklisted`), as `procurement.vendor.blacklisted` says.
- **Only approved vendors** are invited, quote, are awarded and are issued orders. Quotes are recorded while a tender
  is published and before it closes, priced item by item, and its total must equal the items' total including tax
  (422 `quote_total_mismatch`), so ranking, the lowest-quote check and the order use one amount. It is awarded after
  it closes; an award other than the lowest awardable quote needs a justification, and drafts the order from the
  quote's items, which then stay fixed: an awarded order changes only its delivery date, address and terms (422
  `awarded_order`). A closed tender holds its indents only while a quote can still be awarded (unexpired, priced, from a
  vendor still approved). A quote is valid through its `valid_until`
  date (IST) and expired from the next day: an expired quote is 409 `quote_expired` (decided by the owner; see #335).
- **Business dates are Indian** (decided by the owner; see #335). "Today" is the date in Asia/Kolkata (UTC+05:30, a fixed offset:
  India has no daylight saving, and tzdata is not on the approved stack). It decides receipt, invoice and payment
  dates that can't be in the future, when an order becomes overdue, quote expiry, the delivery date drafted at award
  and the date an order started waiting in the report. Timestamps are stored in UTC.
- **Receipts never exceed what is outstanding** on an item. Rejected quantities need a reason and can be delivered
  again. The order becomes `partially_received` or `received`; a received order closes its indents.
- **Cancelling releases what was not delivered.** An issued order with nothing accepted is `cancelled` and releases its
  total. A part-received one is `closed` and releases the value not delivered.
- **Invoices match the accepted value.** Everything invoiced on an order must stay within the accepted value of its
  receipts plus `PROCUREMENT_INVOICE_MATCH_TOLERANCE_PERCENT`. A mismatch is approved only with a note. Payment is
  recorded with its date, reference and TDS deducted (an amount, not computed).
- **Bank account numbers are never stored.** Only the last four digits and the IFSC are kept, because no encryption
  library is on the approved stack yet (decided by the owner; see #335). Vendor bodies are validated in the module, so a 422 never
  echoes the request (and the account number) back. Payment itself happens outside Education OS.
- **A value taken concurrently is 409, never 500:** running numbers, GSTIN and PAN, one quote per vendor and a
  vendor's invoice number, whether the database refuses it at a flush or at the commit. Ids are length-checked, so an
  over-long value is 422 before it reaches the database.
- **Nothing is deleted, and every change is audited.** An `audit_entry` row (actor, action, entity, id) is written in
  the same transaction, until the audit SDK exists. Changes the contract defines events for also publish them to the
  outbox, with exactly the payloads of `events.yaml`.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/finance-operations/procurement/backend[test]"
pytest modules/finance-operations/procurement/backend
```

budget-grants is stood in with an `httpx` mock, so the module's tests need no other module.

### Migrations

```sh
cd modules/finance-operations/procurement/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting, install and CI:** the `finance-operations/procurement` entry in `apps/backend/config/modules.enabled.yaml`
  mounts the router at `/api/v1/procurement`; `py-setup.sh`, the API image, CI and the auto-deploy install it, run its
  tests and upgrade its chain from that entry.
- **budget-grants:** set `PROCUREMENT_BUDGET_GRANTS_URL`. Management approves indents and orders, so management needs
  `budget-grants:availability:read` (granted in #292) and `budget-grants:budget:read` (it has it); department
  admins already have availability.
- **Overspend outside procurement:** the per-line lock serialises procurement's own approvals. Manual spend and
  payroll recorded in budget-grants at the same moment are not covered by it; budget-grants records them as real spend
  and alerts at 80% and 100%.
- **Events:** budget-grants applies `purchase-order.issued`, `purchase-order.cancelled` and `vendor-invoice.paid`
  through its `consumers.handle`. The event-bus relay (#356) runs as the `relay` service in the API deployment (#367)
  and delivers outbox events to the handlers a module registers under the `eos.event_consumers` entry point, but
  budget-grants does not register its handlers yet, and notification has none for procurement. Until budget-grants
  registers them, commitments and spend do not reach budget-grants on a server, and no procurement event leads to a
  notification.

### Assumptions to revisit
- **Departments: not enforced.** The contract allows an indent approver to be limited to their department, but
  identity issues no department claim yet, so procurement cannot apply it: anyone with `procurement:indent:approve`
  sees and decides every indent of the organisation. `department_id` only filters the list. This is enforced once
  identity provides the claim.
- **Names:** `requested_by_name` is empty until identity names are available.
- **Documents:** an issued order has no PDF (`document_id` is null) until the documents SDK exists.
- **Delivery date of an award:** the drafted order is due `delivery_days` after the award (the award day when the
  quote gives none); it is a draft, so it is corrected before submitting.

## Frontend

`frontend/src/widgets/index.ts` exports the dashboard widget. The Finance Staff layout in
`platform/identity/config/dashboards/` places it, and `apps/frontend/config/modules.enabled.yaml` registers the module.

| Widget | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `procurement.purchase-orders-pending` | Finance Staff | `GET /reports/purchase-orders-pending` | `procurement:report:read` |

- **Shows:** orders awaiting approval, issued orders awaiting delivery, overdue deliveries (highlighted when there are
  any) and approved invoices awaiting payment, each with its value; and the ten oldest pending orders with their vendor,
  status, total and the date they started waiting (submitted, or issued).
- **Data:** the widget reads through `src/api/client.ts`, a hand-written typed client that the generated client will replace.
- **States:** loading, empty, and error with a retry when trying again can help. Until the backend answers, the error
  reads "Procurement data is not available yet".
- **Tests:** `cd modules/finance-operations/procurement/frontend && pnpm test` (vitest and Testing Library).

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers and tests |
| `frontend/` | Dashboard widget and its tests |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
