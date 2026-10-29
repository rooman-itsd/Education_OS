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
- Contract: one catalogue of every error code the API answers, by status, in the description; the order create, edit,
  decision (403), cancel, receipt and award responses list the codes they can return. The PRD links the decisions on
  #335.
