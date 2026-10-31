# hr-payroll

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend built; not yet enabled in `apps/backend`; widgets in a later PR)

The institution's staff from joining to exit: employee master, leave, salary and monthly payroll, payslips,
appraisals and the service book. Requirements: [docs/prd.md](docs/prd.md). Sprint batch #336.

## Scope
- **In scope:** employees (joining, editing, exit with the last working day); salary structures of earning and
  deduction lines from an effective date; the service book; leave types, requests, decisions, cancellation, balances and
  carry-forward; monthly payroll runs with loss of pay, adjustments, approval by someone other than the preparer,
  payslips and payment; appraisals (self review, rating); self-service under `/me`; the joinings-and-exits report.
- **Not in scope:**
  - recruitment;
  - statutory return filing (PF, ESI, TDS, professional tax): deductions are salary lines only;
  - making the bank payment (it is recorded after it is made);
  - student attendance and timetables (timetable-attendance).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/hr-payroll`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Scheduler job: `hr-payroll.publish-due-exits` (entry point `eos.scheduler_jobs`), handled through `scheduler.job.due`
  (entry point `eos.event_consumers`)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_hr_payroll/domain/rules.py` | Exact money, leave days and leave years, pro-rata entitlement, carry-forward, payroll periods and due days, the payslip lines with loss of pay, the masked bank account and PAN. Pure Python. |
| application | `application/employees.py` | Employees (add, edit, exit, the exits job), salary structures, the service book, `/me`. |
| | `application/leave.py` | Leave types; apply, decide, cancel; balances with carry-forward; the unpaid days that become loss of pay. |
| | `application/payroll.py` | Payroll runs (start and compute, adjust payslips, submit, approve or return, mark paid), payslips, `/me/payslips`. |
| | `application/appraisals.py` | Appraisal cycles, self review, rating, completion. |
| | `application/reports.py` | Joinings and exits. |
| | `application/common.py`, `access.py`, `errors.py` | Clock and Indian business date, audit and outbox, scoped queries, paging; permission keys; errors with their HTTP status. |
| | `application/jobs.py`, `consumers.py` | The scheduler job declaration and its `scheduler.job.due` handler. |
| infrastructure | `infrastructure/models.py` | 9 `hr_payroll_*` tables, including `audit_entry`. Each has `organisation_id`; money is `Numeric(14, 2)`, leave days `Numeric(5, 1)`. |
| | `infrastructure/config.py` | `HR_PAYROLL_*` settings. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `hr_payroll_0001` with its own version table `hr_payroll_alembic_version`. It applies the `tenant_isolation` policy on Postgres. |

Rules the code keeps:
- **Bank account numbers and PANs are never stored in full** (decided by the owner; see #336). No encryption library
  is on the approved stack, so only the last four digits of the account (with the IFSC and the holder's name) and the
  last four characters of the PAN are kept, returned as `account_last4` and `pan_masked` (`XXXXXX234F`). Full values
  are validated in the module (`invalid_account_number`, `invalid_ifsc`, `invalid_pan`) and then dropped. Employee
  bodies are validated by the module rather than FastAPI, so a 422 never echoes them; error messages never contain a
  submitted value; audit rows hold ids only; no event carries them. On an edit, an absent `bank_account` or `pan` (or
  `user_id`) is left as it is, `null` removes it, and a bank account sent back without its number keeps the one kept.
- **Salary data stays with the employee and payroll readers** (PRD). Salary structures and
  payslips are returned only to the employee themselves and to holders of `hr-payroll:payroll:read`; payslips reach
  the employee only once their run is approved. No event carries an individual's pay: the payroll-run events of
  `events.yaml` carry the run's net total only.
- **Money is exact** (PRD): `Decimal` throughout, `Numeric(14, 2)` in the database, decimal
  strings in the API (`invalid_amount` for more than two places). No floats.
- **Loss of pay.** A run pays everyone on the rolls during the month: from joining (or the 1st) to the last working
  day (or the month's end). Paid days are those days less approved unpaid leave in them (half a day for a half-day
  request). Every line of the salary structure in effect at the end of the employee's days in the month, earnings
  and deductions alike, is paid in proportion `paid days / days in the month` and rounded to the paisa (half up); a
  full month pays the structure exactly. Example: 30,000 basic, 12,000 HRA, 3,600 PF, 3 unpaid days in October
  (28/31): 27,096.77 + 10,838.71 − 3,251.61 = 34,683.87. An employee without a salary is listed in `exceptions` and
  gets no payslip; one without a bank account gets a payslip and an exception.
- **Preparer ≠ approver** (PRD). Whoever started, adjusted a payslip of, or submitted a run
  is one of its preparers and can't decide it (403), even holding `payroll:approve`. A return needs a note and puts the
  run back in review. Nobody adjusts their own payslip or sets their own salary.
- **An approved run is locked.** Approved and paid runs take no adjustment, decision or resubmission (409
  `run_not_in_review`). A salary effective in a month whose run is submitted, approved or paid is refused (409
  `period_locked`), as is unpaid leave in, or an exit before, a month that is approved; corrections go into a later
  month as arrears or deductions.
- **Leave.** Nobody decides their own request (403). Requests are calendar days, both ends included, inside one leave
  year (`HR_PAYROLL_LEAVE_YEAR_START_MONTH`), not before today, joining or after the last working day, never
  overlapping another pending or approved request, for a type that is active and open to the employment type. A paid
  type needs the balance: the year's days (in the year of joining, a share for the months left, rounded down to half a
  day) plus what was carried forward, less approved and pending days. Carry-forward is worked out year by year: what a
  year leaves unused, up to the type's `carry_forward_max`, opens the next. An unpaid type has no balance and its
  approved days are loss of pay. A request is withdrawn by its employee only before it starts; an approved one returns
  its days. Leave starting after a recorded last working day is cancelled.
- **Business dates are Indian** (as procurement; decided by the owner on #335). "Today" is the date in Asia/Kolkata, a fixed
  UTC+05:30 (India has no daylight saving; tzdata is not on the approved stack). It decides leave in the past and
  started, exits due, the current run, a run's lateness, payment dates and the report's defaults. Timestamps are
  stored in UTC.
- **Exits on the last working day** (PRD flow 6). `platform/scheduler` supports module jobs, so
  hr-payroll declares the platform job `hr-payroll.publish-due-exits` (default cron `30 13 * * *` UTC, 19:00 IST,
  after the working day) and handles its `scheduler.job.due`: every employee on notice whose last working day has come
  exits and `hr-payroll.employee.exited` is published, once (the job is idempotent), then it reports
  `hr-payroll.job.finished`. An exit recorded with a last working day of today or earlier is published at once.
- **Appraisals.** HR opens a cycle for a list of employees (all or none). The employee writes and submits the self
  review; someone else with `appraisal:review` rates it (1 to 5) and completes it, which publishes
  `hr-payroll.appraisal.completed`. Nobody rates their own; a completed appraisal does not change.
- **A value taken concurrently is 409, never 500:** employee codes, linked users, leave type codes, a month's run and an
  appraisal per cycle, whether the database refuses it at a flush or at the commit. Leave requests of one employee
  take turns on the employee row, so the balance and overlap checks see each other.
- **Nothing is deleted, and every change is audited.** An `audit_entry` row (actor, action, entity, id) is written in
  the same transaction, until the audit SDK exists. Changes the contract defines events for also publish them to the
  outbox, with exactly the payloads of `events.yaml`.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/finance-operations/hr-payroll/backend[test]"
pytest modules/finance-operations/hr-payroll/backend
```

The suite needs no other module: SQLite in a temporary folder, a frozen clock, and the scheduler's `scheduler.job.due`
delivered to the handler directly.

### Migrations

```sh
cd modules/finance-operations/hr-payroll/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting, install and CI:** a `finance-operations/hr-payroll` entry in `apps/backend/config/modules.enabled.yaml`
  (a separate PR) mounts `eos_hr_payroll.api.router:router` at `/api/v1/hr-payroll`; install, CI and deploy pick it up
  from that entry and upgrade its chain.
- **Scheduler and event bus:** installing the package registers the job and the consumer through their entry points.
  The scheduler creates the job's default schedule itself; the event-bus relay delivers `scheduler.job.due` to
  hr-payroll and `hr-payroll.job.finished` back to the scheduler. Until both run in the deployment, exits dated in the
  future stay `on_notice` and are not published (recording the exit again on or after the day publishes it).
- **identity:** nothing consumes `employee.joined` or `employee.exited` yet, so accounts are neither created nor
  disabled from them; notification has no handlers for hr-payroll's events.
- **Dashboards:** the HR Staff widgets (later PR) read `GET /leave-requests?status=pending`, `GET /payroll-runs/current`
  and `GET /reports/joinings-and-exits`.

### Assumptions to revisit
- **User accounts** (PRD open question 2): HR links an existing identity user with `user_id` when adding or editing
  the employee. `/me/*`, "nobody decides their own" and self reviews rely on that link; an employee without one has no
  self-service.
- **Who holds `self:use`** (open question 3): only the roles listed in `permissions.yaml`; other profiles' staff roles
  need the grant.
- **Statutory deductions** (open question 1): fixed lines, paid in proportion to the paid days like the earnings.
- **Loss of pay** (open question 4): approved unpaid leave only; no staff attendance.
- **Calendar days:** there is no holiday calendar, so weekends and holidays inside a leave request count as leave.
- **Mid-month salary changes:** the month's payslip uses the structure in effect at the end of the employee's days in
  the month; a change mid-month is not split. Use an adjustment for the difference.
- **Late leave decisions:** a run computes loss of pay from leave approved when it is started; unpaid leave approved
  later for that month is handled by adjusting the payslip (while in review) or in a later month.
- **Leave type edits** apply to past years' balances too (they are worked out from the type as it is now).
- **Departments and reportees: not enforced.** The contract allows leave approvers and appraisal reviewers to be
  limited to their department or reportees, but identity issues no department claim yet: anyone with
  `leave:approve` or `appraisal:review` acts on the whole organisation. `department_id` only filters.
- **Run totals in events:** `payroll-run.approved` and `.paid` carry the net total as `events.yaml` defines; in a run
  with one employee it is that employee's pay.
- **Documents:** payslip PDFs and service-record documents have `document_id` null until the documents SDK exists.
- **Rehiring:** an exited employee does not come back; a returning employee is added again with a new code.
- **Runs are computed in the request** (`202`, status `review`); `computing` and `failed` stay in the contract for a
  background computation later.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers and tests |
| `frontend/` | Pages, components, API client and widgets (later PR) |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
