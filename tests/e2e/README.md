# tests/e2e

Full user journeys through `apps/frontend` in a real browser (Playwright). Each run starts its own API
(`apps/backend`, on port 8100) and web dev server (port 5180) with a fresh SQLite database, so it never
touches a dev server you have running, and stops them afterwards.

| Journey | Spec |
|---|---|
| Register an organisation, verify the email, sign-in refused until a super admin approves, sign in, land on the Organisation Admin dashboard | [onboarding/register-approve-signin.spec.ts](onboarding/register-approve-signin.spec.ts) |
| Smoke: the API answers through `/api/` and the site leaves preview mode (also runs against staging) | [smoke/site-is-live.spec.ts](smoke/site-is-live.spec.ts) |
| Organisation Admin signs in; the six platform widgets show the organisation's plan, usage, modules, users and invoices; recent activity waits for platform/audit; the package change switches the plan and an invoice appears | [dashboards/org-admin.spec.ts](dashboards/org-admin.spec.ts) |
| Examination Staff signs in to their dashboard; the examination widgets render and say when data is not available. Data journeys wait for the examinations backend (`fixme`) | [dashboards/examination-staff.spec.ts](dashboards/examination-staff.spec.ts) |
| Facility / Inventory Staff signs in to their dashboard; the four facilities widgets render, show their empty state, then the ticket, low-stock item, overdue asset and booking created through the API. Each part skips until its module is enabled and granted | [dashboards/facility-staff.spec.ts](dashboards/facility-staff.spec.ts) |
| Management (VC, Registrar) signs in to their dashboard; every widget of an enabled module renders and shows its empty state; an application submitted on the public admissions page reaches `admissions.funnel` and the targets management sets show in `fees-accounts.collection-vs-target`. Widgets of modules not enabled yet skip, naming the module and its sprint batch | [dashboards/management.spec.ts](dashboards/management.spec.ts) |
| Research Scholar (research-university) signs in to their dashboard; every widget of an enabled module, the inherited Student ones included, renders and shows its empty state or says the role has no access; a grant recorded with the scholar as principal investigator appears in `budget-grants.my-grants`. The rest skip until their module ships | [dashboards/research-scholar.spec.ts](dashboards/research-scholar.spec.ts) |
| Research Supervisor (research-university) signs in to their dashboard; the inherited Faculty widgets of enabled modules render and show their state; the supervisor's own widgets skip until projects, selection-process and portfolio ship (data journeys `fixme`) | [dashboards/research-supervisor.spec.ts](dashboards/research-supervisor.spec.ts) |
| Finance Staff signs in to their dashboard; the fees-accounts and budget-grants widgets render and show their empty state, then an invoice with a cash payment shows in `fees-accounts.collections-today` and `fees-accounts.outstanding-dues` and a recorded grant in `budget-grants.budget-vs-spend`. `payment-sbiepay.reconciliation` (an integration with no frontend) and `procurement.purchase-orders-pending` (until procurement is enabled) skip; their data journeys are `fixme` | [dashboards/finance-staff.spec.ts](dashboards/finance-staff.spec.ts) |
| Super Admin signs in to their dashboard; an organisation waiting for approval shows in `tenancy.approval-queue` and leaves it once approved; `tenancy.organisations-by-status` and `tenancy.recent-registrations` count and list this run's organisations; a trial set to end in three days shows in `billing.trials-expiring`; the organisation moved to Standard shows in `billing.revenue-by-plan` and `billing.subscriptions-by-plan`. `audit.super-admin-actions` skips until platform/audit exports it (#317) | [dashboards/super-admin.spec.ts](dashboards/super-admin.spec.ts) |
| Research Office (research-university) signs in to their dashboard; `budget-grants.budget-vs-spend` shows its empty state, then the grant the research office records; the rest skip until their module ships | [dashboards/research-office.spec.ts](dashboards/research-office.spec.ts) |
| HR Staff signs in to their dashboard; the hr-payroll and e-office widgets render and show their empty state, then a leave request an employee applies for shows in `hr-payroll.leave-requests` and their joining in `hr-payroll.joinings-and-exits`, the month's payroll run HR starts in `hr-payroll.payroll-run-status`, and a file a colleague forwards to HR in `e-office.files-pending`. Each part skips until its module is enabled (sprint batch #336) | [dashboards/hr-staff.spec.ts](dashboards/hr-staff.spec.ts) |
| Musician (music-academy) signs in to their dashboard; every widget of an enabled module, the inherited Student ones included, renders and shows its empty state (`inventory-equipment.my-loans`, `fees-accounts.fee-dues`, `hostel.notices`, `portfolio.my-portfolio`), then a violin the musician asks to borrow, stocked by facility staff, shows in `inventory-equipment.my-loans`. `facility-booking.my-bookings` skips until PR #395 merges (its data journey is `fixme`), the other widgets until their module ships | [dashboards/musician.spec.ts](dashboards/musician.spec.ts) |
| Music Teacher (music-academy) signs in to their dashboard; the inherited Faculty widgets of enabled modules, `portfolio.reviews-pending` and `facility-booking.bookings-today` render and show their empty state, then a booking later today on a practice room the music teacher approves, set up by facility staff. skill-progress and selection-process skip until their module ships | [dashboards/music-teacher.spec.ts](dashboards/music-teacher.spec.ts) |
| Ensemble / Orchestra Director (music-academy) signs in to their dashboard; `inventory-equipment.low-stock` shows its empty state, then an instrument the store staff stock below its reorder level; productions and selection-process skip until their module ships (data journeys `fixme`) | [dashboards/ensemble-director.spec.ts](dashboards/ensemble-director.spec.ts) |
| Dancer (dance-academy) signs in to their dashboard; every widget of an enabled module, the inherited Student ones included, renders and shows its empty state (`inventory-equipment.my-loans`, `fees-accounts.fee-dues`, `hostel.notices`), then a ghungroo set the dancer asks to borrow, stocked by facility staff, shows in `inventory-equipment.my-loans`. The other widgets skip until their module ships | [dashboards/dancer.spec.ts](dashboards/dancer.spec.ts) |
| Choreographer (dance-academy) signs in to their dashboard; the inherited Faculty widgets of enabled modules and `facility-booking.bookings-today` render and show their empty state, then a booking later today on a studio the choreographer approves, set up by facility staff. productions, selection-process and skill-progress skip until they ship | [dashboards/choreographer.spec.ts](dashboards/choreographer.spec.ts) |
| Production Manager (dance-academy) signs in to their dashboard; `inventory-equipment.low-stock` and `facility-booking.bookings-today` show their empty state, then a costume below its reorder level and a booking later today on a stage the production manager approves, both set up by facility staff. The productions widgets skip until productions ships (sprint batch #318) | [dashboards/production-manager.spec.ts](dashboards/production-manager.spec.ts) |
| Hospitality Trainee (hospitality-institute) signs in to their dashboard; every widget of an enabled module, the inherited Student ones included, renders and shows its empty state, `inventory-equipment.my-loans` among them, then a chef knife set the trainee asks to borrow, stocked by facility staff, shows in `inventory-equipment.my-loans`. `facility-booking.my-bookings` skips until sprint batch #331 exports it, the other widgets until their module ships | [dashboards/hospitality-trainee.spec.ts](dashboards/hospitality-trainee.spec.ts) |
| Chef / Operations Instructor (hospitality-institute) signs in to their dashboard; the inherited Faculty widgets of enabled modules, `facility-booking.bookings-today` and `inventory-equipment.low-stock` render and show their empty state, then an item a store keeper receives below its reorder level shows in `inventory-equipment.low-stock`. skill-progress and productions skip until their module ships | [dashboards/chef-instructor.spec.ts](dashboards/chef-instructor.spec.ts) |
| Industry Coordinator (hospitality-institute) signs in to their dashboard; the field-training, placement-career and productions widgets skip until their module ships | [dashboards/industry-coordinator.spec.ts](dashboards/industry-coordinator.spec.ts) |
| Management Student (management-institute) signs in to their dashboard; every widget of an enabled module, the inherited Student ones included, renders and shows its empty state (`fees-accounts.fee-dues`, `hostel.notices`), then an invoice finance staff raise to the student shows in `fees-accounts.fee-dues` and a notice a warden publishes to every hostel in `hostel.notices`. productions, projects, field-training, placement-career, alumni and lms skip until their module ships (data journeys `fixme`) | [dashboards/management-student.spec.ts](dashboards/management-student.spec.ts) |
| Corporate Mentor (management-institute) signs in to their dashboard; the inherited Faculty widgets of enabled modules and `selection-process.to-judge` render and show their empty state, then a course the organisation admin assigns the mentor to teach in the active term shows in `academic-management.course-roster`, with its empty roster. `selection-process.to-judge`'s data journey is `fixme` until the widget's status filter reaches the API; projects, field-training and productions skip until their module ships | [dashboards/corporate-mentor.spec.ts](dashboards/corporate-mentor.spec.ts) |
| Placement Officer (management-institute) signs in to their dashboard; the field-training, placement-career and productions widgets skip until their module ships (data journeys `fixme`) | [dashboards/placement-officer.spec.ts](dashboards/placement-officer.spec.ts) |
| Lab In-charge (engineering-college) signs in to their dashboard; the four widgets render and show their empty state, then a ticket the lab in-charge raises shows in `maintenance.tickets` with its counts, an item they receive below its reorder level in `inventory-equipment.low-stock`, and a booking made for later today on a resource they approve in `facility-booking.bookings-today`. `inventory-equipment.overdue-loans` has no data journey: the API refuses a due date in the past and the scheduler sweep marks loans overdue (sprint batch #347) | [dashboards/lab-in-charge.spec.ts](dashboards/lab-in-charge.spec.ts) |

The approval step calls the API until the super admin approval queue exists in `apps/frontend`.

## Run

Once: set up Python (`tools/scripts/py-setup.sh`), `pnpm install`, then download the browser:

```
pnpm --filter e2e e2e:install
```

Every time:

```
pnpm --filter e2e e2e            # headless
pnpm --filter e2e e2e:headed     # watch it click through
pnpm --filter e2e e2e:report     # open the HTML report of the last run
```

### Against staging (smoke only)

```
E2E_BASE_URL=https://<staging-host> pnpm --filter e2e e2e                    # bash
$env:E2E_BASE_URL='https://<staging-host>'; pnpm --filter e2e e2e           # PowerShell
```

With `E2E_BASE_URL` set the suite starts no servers and runs only `smoke/`, which reads and never writes:
`/api/v1/health` must answer JSON from Postgres through the site's `/api/` path, and the home page must
show sign-in with no preview banner. Every other journey registers organisations, so it never runs
against a deployed site. A "returned a web page, not the API" failure means the proxy's `/api/`
location does not reach the API host (see `infra/docker/README.md`).

Failures keep a screenshot and a trace in `tests/e2e/.cache/test-results/`
(`pnpm exec playwright show-trace <trace.zip>` replays it step by step).

| Env var | Default | Use |
|---|---|---|
| `E2E_PYTHON` | `.venv/bin/python` (`.venv\Scripts\python.exe` on Windows) | Python with the backend installed |
| `E2E_API_PORT`, `E2E_WEB_PORT` | `8100`, `5180` | Ports for the suite's own servers |

The script is `e2e`, not `test`, on purpose: `web.yml` runs every package's `test` script on each PR,
and this suite needs browsers and both servers. CI runs it in `.github/workflows/system.yml`: after every merge to
`main`, on PRs that change the journeys, `apps/frontend` or the dashboard layouts, and by hand (Actions → system →
Run workflow; a URL there also runs the smoke checks against that site). A failed run keeps the report as the
`e2e-report` artifact. Before the journeys start, `warmup.ts` signs in once so the dev server has compiled every
module (a cold first dashboard load used to outlast the assertions).

## Adding a journey

One folder per journey (`tests/e2e/<journey>/<what>.spec.ts`). Find elements the way a person does:
`getByRole`, `getByLabel` (with `exact: true` when one label is part of another), `getByText`. Give each
run its own organisation slug so journeys never collide.
