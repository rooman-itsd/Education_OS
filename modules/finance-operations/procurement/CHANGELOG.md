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
