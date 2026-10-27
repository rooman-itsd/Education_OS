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
