# Changelog — hr-payroll

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts: employees with exits and service records, salaries, leave types, leave requests with approval,
  monthly payroll runs with separate preparer and approver, payslips, appraisals, self-service and the
  joinings-and-exits report behind the HR Staff widgets; events; permissions and roles.
- PRD (`docs/prd.md`).
- Decided by the owner; see #336: bank account numbers and PANs are not stored in full: the last four digits of the
  account with its IFSC, and the last four characters of the PAN; full values are validated and dropped, never logged,
  audited, published or returned, and a 422 never repeats them. The PRD no longer says "stored encrypted".
- Decided by the owner; see #336: nobody approves or returns a payroll run that holds their own payslip (409
  `own_payslip_in_run`, a new error code on `POST /payroll-runs/{id}/decision`), alongside preparer ≠ approver.
- Rules the backend keeps:
  - from the PRD: money is exact `Decimal`, `Numeric(14, 2)`; preparer ≠ approver for payroll; nobody decides their
    own leave request; salary data never appears in events and is visible only to the employee and holders of
    `hr-payroll:payroll:read`;
  - business dates are Indian (Asia/Kolkata, fixed UTC+05:30) and timestamps UTC, as procurement (#335);
  - `audit_entry` rows in the same transaction until the audit SDK exists; document ids null until the documents SDK
    exists; the exit is published by the platform scheduler job `hr-payroll.publish-due-exits` on the last working day,
    or at once when recorded on or after it;
  - the PRD's open questions take the conservative option, to be confirmed by the owner, listed in the README under
    "Assumptions to revisit".
- Contract 0.2.0 (additive, plus documented errors):
  - every returned row carries `organisation_id`, as the shared cross-tenant leak test needs;
  - employees: `user_id` (HR links the identity user) and `department_name` on input; `pan` and `bank_account` semantics
    (absent unchanged, null removed); `created_at`; department and reference ids are plain strings;
  - salary: `deductions`, `employee_id`, `set_by`; 404 `no_salary`; 409 `period_locked`; nobody sets their own salary;
  - leave: `leave_type_name`, `paid`, `approver_id` on requests; `code`, `paid`, `leave_year` on balances; how days,
    entitlements and carry-forward are counted; cancel is for one's own request only;
  - payroll runs: `note`, `submitted_at`, `approved_at`, `bank_reference`, `due_on`, `late`; payslips: `days_in_month`,
    `adjustments`; how a run is computed; a return needs a note; nobody adjusts their own payslip;
  - `GET /me/appraisals`; `created_at` on appraisals;
  - every error code each operation can answer;
  - `own_payslip_in_run` (409) on a run decision; `period_locked` (409) also on `PUT /employees/{id}` for a
    `joined_on` change reaching an approved or paid month, and on an exit inside a month that is approved or paid;
  - events: `hr-payroll.job.finished` (the scheduler job's report); when `employee.exited` is published.
- Backend (#336): employees (join, edit, exit), salary structures, the service book, leave types and requests with
  balances and carry-forward, monthly payroll runs with loss of pay, adjustments, approval by someone other than the
  preparers, locking and payment, payslips, appraisals, self-service under `/me`, the joinings-and-exits report, and
  every event of `events.yaml` with exactly its payload.
- Scheduler: the platform job `hr-payroll.publish-due-exits` (entry point `eos.scheduler_jobs`) and its
  `scheduler.job.due` consumer (entry point `eos.event_consumers`, `module.yaml` `consumes_events`).
- Alembic chain `hr_payroll_0001`: 9 tables, each with `organisation_id` and the `tenant_isolation` policy on Postgres,
  version table `hr_payroll_alembic_version`.
- `config/env.example` documents every key; `module.yaml` is 0.2.0 and `in-progress`.
- Locking (review of #410): unpaid leave checks every month it touches, not only its first and last; an exit inside
  a month whose approved or paid run pays the employee is refused; `joined_on` does not change into or out of an
  approved or paid month.
- Tests: 68, including the payroll arithmetic with loss of pay, preparer ≠ approver, locking, the masked bank account
  and PAN, the cross-tenant leak test, cross-organisation reads and writes, the migration test, contract drift
  (operations, permissions, error codes, enums, event payloads), the scheduler declaration and the audit trail.
