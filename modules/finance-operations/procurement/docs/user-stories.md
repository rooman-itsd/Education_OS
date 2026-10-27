# procurement: user stories

Roles come from `contracts/permissions.yaml`. Each story names the contract operation that serves it.

## Finance staff

| # | Story | Contract |
|---|---|---|
| F1 | As finance staff I register a vendor with categories, GSTIN, PAN and bank details, and correct them later. Only the last four digits of the account number are kept. | `POST /vendors`, `PUT /vendors/{id}` |
| F2 | As finance staff I approve a vendor before use, and suspend or blacklist one with a reason. | `POST /vendors/{id}/status` |
| F3 | As finance staff I find vendors by status, category or name. | `GET /vendors`, `GET /vendors/{id}` |
| F4 | As finance staff I turn approved indents on one line into a quotation request or tender, publish it, record the quotes received before it closes and compare them, lowest first. | `POST /tenders`, `POST /tenders/{id}/publish`, `POST /tenders/{id}/quotes`, `GET /tenders`, `GET /tenders/{id}` |
| F5 | As finance staff I award a tender; awarding other than the lowest quote needs a justification. The award drafts the purchase order. | `POST /tenders/{id}/award` |
| F6 | As finance staff I prepare a purchase order directly from an approved direct-purchase indent, edit it while it is a draft or returned, and send it for approval. | `POST /purchase-orders`, `PUT /purchase-orders/{id}`, `POST /purchase-orders/{id}/submit` |
| F7 | As finance staff I record a vendor's invoice against an issued order and see how it matches the order and the accepted receipts. | `POST /vendor-invoices`, `GET /vendor-invoices`, `GET /vendor-invoices/{id}` |
| F8 | As finance staff I approve or reject an invoice someone else recorded. | `POST /vendor-invoices/{id}/decision` |
| F9 | As finance staff I record the payment of an approved invoice with its date, reference and TDS deducted. | `POST /vendor-invoices/{id}/mark-paid` |
| F10 | As finance staff I see orders awaiting approval, orders awaiting delivery (and the overdue ones) and invoices awaiting payment. | `GET /reports/purchase-orders-pending` (widget `purchase-orders-pending`) |

## Management

| # | Story | Contract |
|---|---|---|
| M1 | As management I approve, return or reject an indent someone else raised. Approval checks that the budget or grant line can cover the estimated cost and sets the purchase method. | `GET /indents`, `GET /indents/{id}`, `POST /indents/{id}/decision` |
| M2 | As management I approve a purchase order someone else prepared, which issues it, or return it. | `POST /purchase-orders/{id}/decision` |
| M3 | As management I cancel an issued order with nothing received, or close the undelivered remainder of a part-received one. | `POST /purchase-orders/{id}/cancel` |
| M4 | As management I approve or reject a vendor invoice someone else recorded. | `POST /vendor-invoices/{id}/decision` |

## Department admin / HoD

| # | Story | Contract |
|---|---|---|
| D1 | As a department admin I decide indents raised by others. | `GET /indents`, `POST /indents/{id}/decision` |

## Requesters (faculty, research office, facility staff, department admin, finance staff)

| # | Story | Contract |
|---|---|---|
| R1 | As a requester I raise an indent with its items, estimated cost and the budget or grant line it is charged to, edit it while it is a draft or returned, and submit it. | `POST /indents`, `PUT /indents/{id}`, `POST /indents/{id}/submit` |
| R2 | As a requester I follow my indents to order and delivery. | `GET /me/indents`, `GET /indents/{id}` |

## Facility and inventory staff

| # | Story | Contract |
|---|---|---|
| S1 | As facility staff I record goods or services received against an order, accepted or rejected per item. | `POST /purchase-orders/{id}/goods-receipts`, `GET /purchase-orders/{id}/goods-receipts` |

## Other modules

| # | Story | Contract |
|---|---|---|
| X1 | budget-grants records a commitment when an order is issued, releases it when an order is cancelled or its remainder closed, and turns it into actual spend when a vendor invoice is paid. | publishes `procurement.purchase-order.issued`, `.purchase-order.cancelled`, `.vendor-invoice.paid` |
| X2 | notification tells approvers, requesters and vendors about indents, tenders and orders. | publishes `procurement.indent.*`, `.tender.*`, `.purchase-order.issued` |
| X3 | inventory-equipment or asset-management may add stock or register assets from accepted goods. | publishes `procurement.goods-receipt.recorded` |
