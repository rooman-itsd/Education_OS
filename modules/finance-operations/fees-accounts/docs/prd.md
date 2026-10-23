# fees-accounts: product requirements

Owner: Gokula Lakshmi (@gokulalakshmirooman-source) · Status: in progress · Issues #66, #107
Suite E, Finance & operations · tier `common` (every academy type enables it)

## Purpose

Everything an institution charges a person and everything it receives from them: fee heads, fee
structures, invoices, online and offline payments, receipts, concessions, refunds and a ledger per
person, plus the collection reports finance staff and management watch. The contract is
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Users and what they need

| Role | Needs | Dashboard widget |
|---|---|---|
| Applicant | See the application or admission fee due and pay it online | `fees-accounts.fee-due` (`GET /me/dues`) |
| Student | See dues by instalment, pay online, download receipts | `fees-accounts.fee-dues` (`GET /me/dues`) |
| Finance staff | Set up fees, raise invoices, record counter payments, refund, request concessions, follow up dues | `fees-accounts.collections-today` (`GET /reports/collections`), `fees-accounts.outstanding-dues` (`GET /reports/outstanding`) |
| Management (VC, Registrar) | Collections against target; approve concessions | `fees-accounts.collection-vs-target` (`GET /reports/collection-vs-target`) |
| Org admin | Read-only oversight, set targets | — |

## Main flows

1. **Set up.** Finance staff create fee heads (tuition, hostel, examination and so on) and a fee structure
   per academic year, optionally per programme and student category: items per head, instalments with
   percentages and due dates, part-payment allowed or not, optional late-fee rule. Publish it.
2. **Raise invoices.** One invoice per person per instalment, raised one at a time, in bulk for a cohort,
   or automatically from an event (admission accepted). Ad hoc invoices (fines, certificate fees) use lines
   instead of a structure.
3. **Pay online.** The payer opens `/me/dues` and pays; fees-accounts asks payment-sbiepay for a session
   (purpose `fee`) and sends the browser to the gateway. On `payment-sbiepay.payment.succeeded` the payment
   is applied, a receipt is issued and `fees-accounts.payment.received` is published; when the balance
   reaches zero, `fees-accounts.invoice.paid`.
4. **Pay at the counter.** Finance staff record cash, cheque, demand draft or bank transfer; a receipt is
   issued at once. A bounced cheque is voided, which cancels its receipt and restores the balance.
5. **Concessions.** Finance staff request a scholarship, waiver or other concession on an invoice with a
   reason and a supporting document; management approve or reject it. The requester can never approve their own.
6. **Refunds.** Full or partial, never above what was paid. Online payments are refunded through the gateway.
7. **Overdue.** A daily job marks invoices overdue, adds late fees per the structure's rule and publishes
   `fees-accounts.invoice.overdue` once per invoice; notification sends reminders before and after the due date.
8. **Reports.** Collections for a day by mode and head; outstanding with ageing; collected against monthly targets.

## Rules

- Money is stored and exchanged as exact decimals (decimal strings in the API); no floating point.
- Invoice and receipt numbers are sequential per organisation and never reused; cancelled ones stay visible.
- Nothing financial is deleted: invoices are cancelled, payments voided or refunded, all with a reason.
- A published fee structure is not edited; it is archived and replaced. Invoices already raised keep their amounts.
- Applying a gateway payment is idempotent by gateway reference; a repeated event changes nothing.
- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- A person sees only their own invoices, payments and receipts (`/me/*`); staff access needs the permission in `permissions.yaml`.
- No dependency on another module being enabled: if admissions is off, invoices are raised by hand.

## Integration points

| Direction | With | How |
|---|---|---|
| Calls | payment-sbiepay | `POST /payments` (purpose `fee`), `POST /payments/{reference}/refunds` |
| Consumes | payment-sbiepay | `payment.succeeded`, `payment.failed`, `payment.refunded` |
| Consumes | admissions | `admissions.application.accepted` raises the confirmation fee invoice (person id still to agree, #192) |
| Consumes | hostel | `hostel.allocation.confirmed` invoices the hostel fee of the structure for that `room_type` and year; `.cancelled` cancels it if unpaid (#175) |
| Consumes | transport | `transport.pass.issued` invoices the fee of the structure for that `route_id` (staff only if `invoice_staff_transport`); `.cancelled` cancels it if unpaid (#175) |
| Consumes | library | `library.fine.raised` invoices the fine when `invoice_library_fines` is on; `.waived` cancels it. Library consumes `fees-accounts.invoice.paid` (`source_module=library`) to mark the fine paid (#175) |
| Serves | examinations | `GET /dues?person_id=&source_module=examinations&source_reference=<exam_cycle_id>`, permission `fees-accounts:dues:read`; examinations decides eligibility (#183) |
| Publishes | anyone | `invoice.issued`, `invoice.paid`, `invoice.overdue`, `payment.received` and the rest of `events.yaml` |
| Platform | identity, audit, documents, notification, scheduler | through `packages/sdk` |
| References | student-information, academic-management | `person_id`, `programme_id` by id; names cached from their events |

## Out of scope

- Payroll, budgets and purchase payments (hr-payroll, budget-grants, procurement).
- The platform's own subscription invoices (platform/billing).
- A general ledger or accounting package. A later integration can export the ledger.

## Open questions (for review)

1. `admissions.application.accepted` exists (admissions contract) but carries no person or user id, while
   invoices key on `person_id`. Asked Praveen on #192 to add the applicant's user id; until then the event is
   handled only when the payload carries one.
2. Does enrolment-registration also raise tuition invoices by event, or are they raised in bulk by finance staff?
3. Whether any fee head needs tax (GST) lines. Not modelled yet.
4. Dashboard ids: Applicant uses `fees-accounts.fee-due` and Student uses `fees-accounts.fee-dues`. Both are
   served by `GET /me/dues` and both ship as widgets (issue #107 lists both); merging them is the layout owner's call.
