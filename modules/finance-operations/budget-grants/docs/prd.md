# budget-grants: product requirements

Owner: Gokula Lakshmi (@gokulalakshmirooman-source) · Status: draft for review · Issue #66
Suite E, Finance & operations · tier `common`

## Purpose

Plan the institution's money and track externally funded grants: annual budgets by head and department,
reappropriation between lines, commitments and actual spend, grants with their own lines and investigators,
funds received, and utilisation certificates (UCs) for funders. Contract: `contracts/openapi.yaml`,
`events.yaml`, `permissions.yaml`.

## Users

| Role | Needs | Dashboard widget |
|---|---|---|
| Finance staff | Prepare budgets, record spend, manage grants, certify UCs | `budget-grants.budget-vs-spend` (`GET /reports/budget-vs-spend`) |
| Research office | Record grants and funds received, prepare UCs, watch grant spend | `budget-grants.budget-vs-spend` (`scope=grants`) |
| Management | Approve budgets, reappropriations and UCs | — |
| Department admin / HoD | See their department's budget | — |
| Investigators (faculty, research supervisor, research scholar) | See their grants, balance and next UC due; pick a grant line when raising an indent | `budget-grants.my-grants` (`GET /me/grants`) |

## Main flows

1. **Budget.** Finance staff create budget heads, then a budget per financial year for the institution
   or a department, with an allocation per head. Submit; management approve (never the preparer).
2. **Reappropriation.** Move money between lines of an approved budget, with a reason and approval.
3. **Spend.** procurement checks `GET /availability` before approving an indent. A purchase order issued
   becomes a commitment; a vendor invoice paid turns it into actual spend; a cancelled order releases it.
   A paid payroll run is charged to the salary head. Anything else is recorded by hand with a voucher.
   Crossing 80% and 100% of a line publishes `budget-grants.line.threshold-reached`.
4. **Grants.** Record the sanction (funder, scheme, amount, period, investigators, lines per head), then each
   instalment received. Spend against grant lines works like budget lines.
5. **Utilisation certificates.** Draft for a period from the records (received, spent by head, balance);
   certify; generate the PDF; record when it is sent. Reminders 30 and 7 days before due.
6. **Close a grant.** Record whether the unspent balance is returned or carried over.

## Rules

- Spend never exceeds what is available on a line unless reappropriated first; the check is enforced on manual
  entries and offered to procurement through `/availability`.
- Nothing is deleted: entries are reversed with a reason; approved budgets are changed only by reappropriation.
- Preparer and approver are always different people (budgets, reappropriations, UCs).
- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- Money is exact decimal; no floating point.

## Integration points

| Direction | With | How |
|---|---|---|
| Called by | procurement | `GET /lines`, `GET /availability` |
| Consumes | procurement | `purchase-order.issued` (commitment), `purchase-order.cancelled` (release), `vendor-invoice.paid` (commitment to spent), all on `line_id` (procurement contract, #173) |
| Consumes | hr-payroll | `payroll-run.paid`: `net_total` is charged to the salary head (`BUDGET_GRANTS_SALARY_BUDGET_HEAD_CODE`) of the institution-wide approved budget of the financial year of `paid_on` (hr-payroll contract, #171) |
| Publishes | notification and others | `line.threshold-reached`, `utilisation-certificate.due` and the rest of `events.yaml` |
| Platform | identity, audit, documents, notification, scheduler | through `packages/sdk` |

## Out of scope

- Fee income (fees-accounts) and the platform's own billing.
- Full double-entry accounting; this module tracks budgets and spend against them.
- Funder portals. Certificates are produced as PDFs and sent outside the system.

## Open questions (for review)

1. The funder's UC format differs by agency; the PDF layout is one generic template for now.
2. Decided (#221): the commitment starts at the purchase order, so `/availability` is a check, not a
   reservation, and `procurement.indent.approved` reserves nothing.
3. Payroll spend is charged to one institution-wide salary head. Department-wise salary budgets would need a
   department breakdown in `hr-payroll.payroll-run.paid`.
