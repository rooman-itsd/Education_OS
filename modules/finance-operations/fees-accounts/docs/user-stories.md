# fees-accounts: user stories

Each story names the contract operation that serves it (`contracts/openapi.yaml`). Tests are linked here as the
backend lands.

## Applicant and student

| # | Story | Contract |
|---|---|---|
| S1 | As an applicant I see the admission fee I owe and its due date on my dashboard. | `GET /me/dues` (widget `fee-due`) |
| S2 | As a student I see my unpaid and part-paid fees, the earliest due first, with what is overdue. | `GET /me/dues` (widget `fee-dues`) |
| S3 | As a student I pay a fee online and come back to the page I started from. | `POST /invoices/{id}/pay`, then payment-sbiepay |
| S4 | As a student I see all my invoices and download my receipts. | `GET /me/invoices`, `GET /me/receipts`, `GET /receipts/{id}` |

## Finance staff

| # | Story | Contract |
|---|---|---|
| F1 | As finance staff I set up fee heads (tuition, hostel, examination...). | `GET/POST /fee-heads`, `PUT /fee-heads/{id}` |
| F2 | As finance staff I define a fee structure for a year, optionally for a programme, student category, hostel room type or transport route, with instalments and a late-fee rule, and publish it. | `POST /fee-structures`, `PUT /fee-structures/{id}`, `POST .../publish`, `POST .../archive` |
| F3 | As finance staff I raise an invoice for one person, from a structure instalment or from ad hoc lines. | `POST /invoices` |
| F4 | As finance staff I raise one instalment for a whole cohort; people already invoiced are skipped. | `POST /invoices/bulk`, `GET /invoices/bulk/{id}` |
| F5 | As finance staff I record a counter payment (cash, cheque, DD, bank transfer) and a receipt is issued at once. | `POST /invoices/{id}/payments` |
| F6 | As finance staff I void a bounced cheque; its receipt is cancelled and the balance comes back. | `POST /payments/{id}/void` |
| F7 | As finance staff I refund all or part of a payment, never more than was paid. | `POST /payments/{id}/refunds` |
| F8 | As finance staff I cancel an invoice raised in error, if nothing is paid on it. | `POST /invoices/{id}/cancel` |
| F9 | As finance staff I request a scholarship or waiver on an invoice with a reason. | `POST /concessions` |
| F10 | As finance staff I look up any person's statement with a running balance. | `GET /accounts/{person_id}/statement` |
| F11 | As finance staff I see today's collections by mode and head against yesterday. | `GET /reports/collections` (widget `collections-today`) |
| F12 | As finance staff I see outstanding and overdue dues with ageing. | `GET /reports/outstanding` (widget `outstanding-dues`) |
| F13 | As finance staff I choose whether library fines and staff transport passes are invoiced. | `GET/PUT /settings` |

## Management and org admin

| # | Story | Contract |
|---|---|---|
| M1 | As management I approve or reject a concession someone else requested. | `POST /concessions/{id}/decision` |
| M2 | As management I set monthly collection targets and see collections against them. | `PUT /collection-targets`, `GET /reports/collection-vs-target` (widget `collection-vs-target`) |

## Other modules (through events or the API)

| # | Story | Contract |
|---|---|---|
| X1 | When an online payment succeeds, the invoice is paid and a receipt issued, exactly once. | consumes `payment-sbiepay.payment.succeeded` |
| X2 | When a hostel allocation is confirmed, the hostel fee for that room type and year is invoiced; a cancelled allocation cancels it if unpaid. | consumes `hostel.allocation.confirmed`, `.cancelled` |
| X3 | When a transport pass is issued, the route fee is invoiced (staff only if the setting says so); a cancelled pass cancels it if unpaid. | consumes `transport.pass.issued`, `.cancelled` |
| X4 | When a library fine is raised and the organisation invoices fines, it is invoiced; a waived fine cancels it. Library marks the fine paid from `fees-accounts.invoice.paid`. | consumes `library.fine.raised`, `.waived` |
| X5 | Examinations reads a candidate's outstanding exam fee for a cycle at the eligibility cut-off. | `GET /dues` |
| X6 | When an admission offer is accepted, the confirmation fee is invoiced. | consumes `admissions.application.accepted` (needs a person id, see PRD open questions) |
