# procurement

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend built; widget and registration in their own PRs)

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
- **An order is issued only if its line covers its total** (decided on #129). Approving a purchase order asks
  budget-grants `GET /availability` for the order total and `GET /expenditures` (commitments) for the line, with the
  approver's token, so the approver needs `budget-grants:availability:read` and `budget-grants:budget:read`.
  budget-grants records a commitment only when `procurement.purchase-order.issued` reaches it, so the totals of this
  organisation's issued orders on the line that budget-grants has not recorded yet are taken off what it reports.
  Approvals on one line are serialised by a Postgres transaction-level advisory lock, so two approvals cannot spend
  the same balance. A line that can't cover the total is 422 `insufficient_budget`; budget-grants unreachable or
  refusing is 503 `budget_check_unavailable`. Either way the order stays submitted and nothing is published.
- **The purchase method follows the value.** Up to `PROCUREMENT_DIRECT_PURCHASE_LIMIT` a direct purchase, up to
  `PROCUREMENT_QUOTATION_LIMIT` quotations, above it a tender. The limits have no default: until both are set, approval
  is 422 `purchase_limits_not_configured` (decided on #129). A tender may use a stricter method than its indents need,
  never a looser one, judged on their combined value too. Only direct-purchase indents become an order directly, and
  only while their combined estimate and the order's own total stay within the direct limit (422 `tender_required`), so
  a purchase can't be split into direct orders or priced above what was approved.
- **An indent belongs to one open tender or order at a time.** Indents combined into one tender or order share one line.
  The indents are locked while checked, so two requests for the same indent take turns. When an order is cancelled
  with nothing received, its indents can be ordered again. A tender that can no longer be awarded (a draft past its
  closing date, or one that closed without a quote) lets its indents go; the contract has no way to cancel a tender.
- **Blacklisting is final** (409 `vendor_blacklisted`), as `procurement.vendor.blacklisted` says.
- **Only approved vendors** are invited, quote, are awarded and are issued orders. Quotes are recorded while a tender
  is published and before it closes. It is awarded after it closes; an award other than the lowest valid quote needs
  a justification, and drafts the order from the quote's priced items. A quote is valid through its `valid_until`
  date (IST) and expired from the next day: an expired quote is 409 `quote_expired` (decided on #129).
- **Business dates are Indian** (decided on #129). "Today" is the date in Asia/Kolkata (UTC+05:30, a fixed offset:
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
  library is on the approved stack yet (decided on #129). Vendor bodies are validated in the module, so a 422 never
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
- **Mounting, install and CI:** an entry `finance-operations/procurement` in `apps/backend/config/modules.enabled.yaml`
  (a separate PR) mounts the router at `/api/v1/procurement`; `py-setup.sh`, the API image, CI and the auto-deploy then
  install it, run its tests and upgrade its chain.
- **budget-grants:** set `PROCUREMENT_BUDGET_GRANTS_URL`. Management approves indents and orders, so management needs
  `budget-grants:availability:read` (a separate budget-grants PR) and `budget-grants:budget:read` (it has it); department
  admins already have availability.
- **Overspend outside procurement:** the per-line lock serialises procurement's own approvals. Manual spend and
  payroll recorded in budget-grants at the same moment are not covered by it; budget-grants records them as real spend
  and alerts at 80% and 100%.
- **Events:** budget-grants applies `purchase-order.issued`, `purchase-order.cancelled` and `vendor-invoice.paid`
  through its `consumers.handle`, but until the event bus exists nothing delivers them. A relay must read the outbox and
  call it. Until then, commitments and spend do not reach budget-grants on a server. The same holds for notification.

### Assumptions to revisit
- **Departments:** an indent approver sees every indent of the organisation; departments are not available to
  modules yet, so "one's department" can't be applied. `department_id` filters the list.
- **Names:** `requested_by_name` is empty until identity names are available.
- **Documents:** an issued order has no PDF (`document_id` is null) until the documents SDK exists.
- **Delivery date of an award:** the drafted order is due `delivery_days` after the award (the award day when the
  quote gives none); it is a draft, so it is corrected before submitting.

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
