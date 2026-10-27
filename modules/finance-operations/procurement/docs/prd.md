# procurement: product requirements

Owner: Gokula Lakshmi (@gokulalakshmirooman-source) · Status: draft for review · Issue #66
Suite E, Finance & operations · tier `common`

## Purpose

Buying goods and services from request to payment: vendors, indents (purchase requests), quotation requests
and tenders, purchase orders, goods receipts and vendor invoices. Every purchase is charged to a budget or grant
line in budget-grants. Contract: `contracts/openapi.yaml`, `events.yaml`, `permissions.yaml`. Stories:
[user-stories.md](user-stories.md).

## Users

| Role | Needs | Dashboard widget |
|---|---|---|
| Finance staff | Manage vendors, run quotations and tenders, prepare orders, record and pay invoices | `procurement.purchase-orders-pending` (`GET /reports/purchase-orders-pending`) |
| Management | Approve indents, orders and invoices | — |
| Department admin / HoD | Approve their department's indents | — |
| Facility / inventory staff | Raise indents, record goods received | — |
| Faculty, research office | Raise indents against their budget or grant line and follow them | — |

## Main flows

1. **Vendors.** Register with categories, GSTIN, PAN and bank details; approve before use; suspend or blacklist with a reason.
2. **Indent.** The requester describes items, estimated cost and the budget or grant line (`GET /lines` from budget-grants)
   and submits. The approver decides; approval checks `GET /availability` and sets the purchase method from the estimated
   value and the institution's limits (`PROCUREMENT_DIRECT_PURCHASE_LIMIT`, `PROCUREMENT_QUOTATION_LIMIT`).
3. **Quotation or tender.** For methods other than direct: invite vendors, record quotes before closing, compare
   (lowest first), award. Awarding other than the lowest needs a justification.
4. **Purchase order.** Drafted from the award or directly from the indent; submitted; approved by someone other than
   the preparer. Approval issues it: PDF, vendor notified, `procurement.purchase-order.issued` (budget commitment).
5. **Receipt.** Goods or services received are recorded per item as accepted or rejected.
6. **Invoice.** The vendor's invoice is recorded against the order, matched with the order and accepted receipts,
   approved by someone other than the recorder, then marked paid: `procurement.vendor-invoice.paid` (actual spend).
7. **Cancel.** An order with nothing received is cancelled, or its undelivered remainder closed; the commitment is released.

## Rules

- One purchase order is charged to one budget or grant line; indents combined into one order or tender share that line.
- Preparer and approver are different people for indents, orders and invoices.
- Only approved vendors receive tenders and orders.
- Nothing is deleted: indents are rejected, orders cancelled, invoices rejected, each with a reason.
- Bank account numbers are returned masked. No encryption library is on the approved stack yet, so only the last four
  digits and the IFSC are kept; the full number is never stored (decided on #129).
- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- Money is exact decimal; no floating point.

## Integration points

| Direction | With | How |
|---|---|---|
| Calls | budget-grants | `GET /lines`, `GET /availability` (budget-grants contract 0.2.0), with the caller's token; management has `budget-grants:availability:read` for indent approval |
| Publishes | budget-grants | `purchase-order.issued`, `purchase-order.cancelled`, `vendor-invoice.paid` |
| Publishes | inventory-equipment, asset-management | `goods-receipt.recorded` |
| Publishes | notification | indent, tender and order events |
| Platform | identity, audit, documents, notification | through `packages/sdk` |

## Out of scope

- Stock and asset registers (facilities modules), which react to `goods-receipt.recorded`.
- Making the bank payment itself; payment is recorded after it is made.
- Government e-procurement portals.

## Open questions (for review)

1. Purchase limits per method differ by institution and funding source. They are configuration with no default; to be
   confirmed with each institution. Decided on #129: until both limits are set, indent approval is refused with 422
   `purchase_limits_not_configured`; no method is guessed.
2. Should facilities consume `goods-receipt.recorded` to add stock or assets? To agree with the facilities owner (Ashritha).
3. TDS on vendor payments is recorded as an amount; it is not computed.
