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
- `docs/user-stories.md`; the PRD records the decisions on purchase limits and bank account numbers (#129).
- Contract (decisions on #129): purchase order approval checks the order total against its line (422
  `insufficient_budget`, 503 `budget_check_unavailable`); an expired quote is not awarded (409 `quote_expired`);
  business dates are Indian (Asia/Kolkata). Also documents 409 `vendor_blacklisted` and 422 `tender_required` on edit.
- Backend (#129):
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
- Tests: 49, including the cross-tenant leak test, cross-organisation reads and writes, the migration test, contract
  drift (operations, permissions, enums, event payloads) and the audit trail.
