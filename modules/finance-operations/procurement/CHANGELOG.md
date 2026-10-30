# Changelog — procurement

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts: vendors, indents with budget check, quotation requests and tenders with comparative statement and
  award, purchase orders with approval, goods receipts, vendor invoices with matching, approval and payment,
  and the report behind the purchase-orders-pending widget; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contracts: `procurement.indent.approved` no longer says budget-grants may reserve the amount; the commitment
  starts at `procurement.purchase-order.issued`, as the budget-grants PRD sets out.
- Contract 0.2.0: vendors, indents, tenders, purchase orders, goods receipts and vendor invoices carry
  `organisation_id` (additive), as the shared cross-tenant leak test needs. Indent approval documents its errors:
  422 `insufficient_budget` or `purchase_limits_not_configured`, 503 `budget_check_unavailable`. Only the last four
  digits of a vendor's bank account are kept.
- `docs/user-stories.md`; the PRD records the decisions on purchase limits and bank account numbers (#335).
- Contract (decisions recorded on #335): purchase order approval checks the order total against its line (422
  `insufficient_budget`, 503 `budget_check_unavailable`); an expired quote is not awarded (409 `quote_expired`);
  business dates are Indian (Asia/Kolkata). Also documents 409 `vendor_blacklisted` and 422 `tender_required` on edit.
- PRD: vendor bank details are the last four digits and the IFSC only; the full account number is never stored,
  because payments are made outside Education OS. This replaces "stored encrypted" (#335).
- Contract, after review (#294): cancelling a draft or returned order (409 `not_cancellable` otherwise); `invalid_date`
  on order create, edit and submit and on goods receipts; `quantity_exceeds_outstanding` and `order_not_open` on
  receipts; quotes need priced items whose total matches (`price_required`, `quote_total_mismatch`); an awarded order
  keeps its quote's items (`awarded_order`); a tender holds its indents only while it can still be awarded; department
  scoping of indent approvers is stated as not enforced; story S2 covers the purchase order list and detail.
- Backend (#335, was #129):
  - vendors: registration, approval, suspension and blacklisting with a reason; only the last four digits of a bank
    account are kept;
  - indents: raise, edit, submit; approval by someone other than the requester checks budget-grants `GET /availability`
    with the approver's token and sets the purchase method from the configured limits;
  - quotation requests and tenders: create from approved indents on one line, publish, record quotes until closing,
    compare lowest first, award (a justification for other than the lowest), which drafts the order;
  - purchase orders: direct from a direct-purchase indent or from an award, approved by someone other than the
    preparer, which issues them; cancel or close the undelivered remainder;
  - goods receipts per item, accepted or rejected, never above what is outstanding;
  - vendor invoices matched with the order and accepted receipts, approved by someone other than the recorder, and
    marked paid;
  - the purchase-orders-pending report;
  - every event of `events.yaml`, with exactly its payload.
- Alembic chain `procurement_0001`: 10 tables, each with `organisation_id` and the `tenant_isolation` policy on Postgres.
- Audit trail: `procurement_audit_entry` records every state change in the same transaction (actor, action, entity, id),
  until the audit SDK exists, as in hostel, helpdesk and budget-grants.
- `config/env.example` lists every key; `module.yaml` status is `in-progress`.
- Tests: 80, including the cross-tenant leak test, cross-organisation reads and writes, the migration test, contract
  drift (operations, permissions, enums, event payloads) and the audit trail.
- Fixes from an independent review, each with a regression test:
  - one indent could be put on two orders by two requests at once: the indents are now locked while checked;
  - direct-purchase indents could be combined, or priced, above the direct limit in one direct order: 422 `tender_required`;
  - a value taken concurrently (a running number, GSTIN or PAN, a quote, an invoice number) answered 500: now 409;
  - an over-long `department_id` or `document_id` answered 500 on Postgres: now 422;
  - indents stayed held by a tender that could no longer be awarded: now released;
  - a blacklisted vendor could be approved again: blacklisting is final;
  - an unreadable answer from budget-grants read as "insufficient budget": now 503 `budget_check_unavailable`;
  - a 422 on a vendor body echoed the bank account number back: no longer;
  - reopening indents after a cancelled order was audited as `indent.approved`: now `indent.reopened`.
- Decisions recorded on #335 (was #129), each with tests:
  - a purchase order is issued only if its line covers its total: `GET /availability` for the total, less this
    organisation's issued orders budget-grants has not recorded yet (`GET /expenditures`), under a per-line Postgres
    advisory lock; otherwise 422 `insufficient_budget` (or 503) and the order stays submitted;
  - business dates follow Asia/Kolkata (IST): future-date checks, overdue, quote expiry, the drafted delivery date and
    the report's dates, with tests on both sides of IST midnight;
  - an expired quote is not awarded (409 `quote_expired`); a quote is valid through its `valid_until` date, and the
    lowest valid quote sets whether a justification is needed.
- Second review (#295), each with a regression test:
  - whoever created, edited or submitted an order at any point cannot approve it (pushed by the reviewer);
  - a draft or returned order can be cancelled, with no event, and its indents can be ordered again;
  - `delivery_by` cannot be before today (on create, edit and submit), and `received_on` cannot be before the order
    was issued (422 `invalid_date`);
  - the README states that department scoping of indent approvers is not enforced until identity has a department
    claim.
- Third review (#295), each with a regression test:
  - a quote is priced item by item and its total must equal the items' total including tax (`quote_total_mismatch`),
    so a typed total can no longer win the ranking while the order is priced from different items;
  - a closed tender holds its indents only while one of its quotes can still be awarded (unexpired, priced, vendor
    approved), so an expired or unpriced quote no longer locks them;
  - an awarded order keeps the quote's items and prices; only its delivery date, address and terms change
    (`awarded_order`);
  - running numbers take a per-organisation Postgres advisory lock before counting, as maintenance does.
- Contract: one catalogue of every error code the API answers, by status, in the description; the order create, edit,
  decision (403), cancel, receipt and award responses list the codes they can return. The PRD links the decisions on
  #335.
- Tests: a contract-drift test fails if the backend raises an error code the contract doesn't list; the running-number
  lock has a test of its statement (the race itself was run on PostgreSQL 16). The README states the unawardable-tender
  rule fully, cancelling an unissued order, and the order date rules.
- Fourth review (#295), with a regression test: a tender that let its indents go while its only vendor was suspended
  could, once the vendor was approved again, be awarded for indents another order had taken (two orders for one
  indent). The award now locks and checks the tender's indents (409 `indent_in_use`); the contract's award response
  lists it.
- Widget `purchase-orders-pending` (Finance Staff), with loading, empty and error-with-retry states; 18 tests. Frontend
  test dependencies came in their own PR.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/procurement`) and
  `apps/frontend/config/modules.enabled.yaml`; the README documents the widget, and its events note names what is
  still missing now that the event-bus relay exists (budget-grants registering its consumers, a deployment running it).
