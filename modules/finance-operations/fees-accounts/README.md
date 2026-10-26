# fees-accounts

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend and widgets built; mounting in apps/backend pending)

Fee structures, invoices, online and counter payments, receipts, concessions, refunds, ledgers and the collection
reports behind the Applicant, Student, Finance Staff and Management dashboards. Requirements:
[docs/prd.md](docs/prd.md); stories: [docs/user-stories.md](docs/user-stories.md).

## Scope
- **In scope:** what an institution charges a person and what it receives from them.
- **Not in scope:**
  - payroll, budgets and purchase payments (hr-payroll, budget-grants, procurement);
  - the platform's own subscription invoices (billing);
  - a general ledger.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/fees-accounts`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_fees_accounts/domain/rules.py` | Exact money, instalment splits that never lose a paisa, late fees (flat or per day, grace, cap), status from balance, ageing, proportional allocation, concessions, academic years. Pure Python. |
| application | `application/service.py` | Fee heads, structures, invoices (single, bulk, from events), counter and online payments, receipts, voids, refunds, concessions, statements, `/me/*`, `/dues`, settings, targets. |
| | `application/reports.py` | Collections for a day and collected against target, both net of refunds completed in the period (a refund counts on the day it completed, by the mode and fee heads of the payment it returns); outstanding with ageing. |
| | `application/consumers.py` | Handlers for every event in `module.yaml` `consumes_events`. Each is idempotent and runs in a fresh transaction of the event's organisation; they refuse to run inside `platform_scope`. |
| | `application/jobs.py` | `run_daily`: late fees and `invoice.overdue` once per invoice. |
| infrastructure | `infrastructure/models.py` | 13 `fees_accounts_*` tables, including `audit_entry` (migration `fees_accounts_0002`). Each has `organisation_id`; money is `Numeric(12, 2)`. |
| | `infrastructure/payment_adapter.py` | HTTP client for payment-sbiepay. It forwards the caller's token. |
| | `infrastructure/config.py` | `FEES_ACCOUNTS_*` settings. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `fees_accounts_0001` with its own version table. It applies the `tenant_isolation` policy on Postgres. |

Rules the code keeps:
- **Money is exact.** It uses `Decimal` throughout, and amounts are decimal strings in the API.
- **Numbers are sequential.** Invoice and receipt numbers are sequential per organisation and never reused; the counter row is locked.
- **Nothing financial is deleted.** Invoices are cancelled, payments voided or refunded, each with a reason.
- **Every change is audited.** A `fees_accounts_audit_entry` row (actor, action, entity, id) is written in the same transaction, for API calls, consumed events and the daily job alike, until the audit SDK exists. The `fees-accounts.*` events of the contract go to the outbox too.
- **Online payments are applied once.** They are idempotent by the gateway reference.
- **Refunds never exceed what was paid.** Refunds the gateway hasn't settled yet count against the balance.
- **A refund reduces what was paid.** The balance comes back unless a concession or cancellation covers it, so the statement and the dues always agree. A fully refunded invoice can then be cancelled.
- **A concession is capped at what is invoiced.** A request above the invoice total is refused; an approval is capped at total plus late fee less earlier concessions (not at what is still due, so a later void doesn't shrink it). Money paid above what is due shows as the invoice's `credit`, for finance staff to refund.
- **Refunds made at the adapter are recorded.** A `payment-sbiepay.payment.refunded` event for a payment of ours that fees-accounts didn't start is recorded against that payment and completed, so the ledger follows the money.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/finance-operations/fees-accounts/backend[test]"
pytest modules/finance-operations/fees-accounts/backend
```

The tests mount only this module's router, issue tokens with `eos_core.security` and use a throwaway SQLite file.
Every file also passes alone.

### Migrations

```sh
cd modules/finance-operations/fees-accounts/db
alembic upgrade head                     # uses EOS_DATABASE_URL
alembic -x url=postgresql+psycopg://... upgrade head
```

### Needs from the host repo
- **Mounting:** mount `eos_fees_accounts.api.router:router` under `/api/v1/fees-accounts` and add the package to `apps/backend`.
- **CI:** add `-e "modules/finance-operations/fees-accounts/backend[test]"` to `tools/scripts/py-setup.sh`, and the backend path to `.github/workflows/api.yml`, so CI runs these tests, also on Postgres.
- **Events:** until the event bus exists, relay each consumed event to `application.consumers.handle(db, name, payload)`.
- **Daily job:** until the scheduler exists, call `application.jobs.run_daily(db)` once a day.
- **Online payments:** set `FEES_ACCOUNTS_PAYMENT_ADAPTER_URL` and `FEES_ACCOUNTS_PAYMENT_RETURN_URL`. The adapter needs the organisation's merchant account.

### Assumptions to revisit
- **People are identity users.** Until student-information maps users to people, a person's `person_id` is their identity user id; `/me/*` relies on it.
- **Days are UTC.** That applies to due dates, overdue and reports, until the organisation's time zone is available to modules.
- **Applicant invoices from admissions** are raised only when `admissions.application.accepted` carries a person or user id (#192).

## Frontend

`frontend/src/widgets/index.ts` exports the five dashboard widgets. The role layouts in
`platform/identity/config/dashboards/` place them, and `apps/frontend/config/modules.enabled.yaml` registers the module.

| Widget | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `fees-accounts.fee-due` | Applicant | `GET /me/dues` | `fees-accounts:self:read` |
| `fees-accounts.fee-dues` | Student | `GET /me/dues` | `fees-accounts:self:read` |
| `fees-accounts.collections-today` | Finance Staff | `GET /reports/collections` | `fees-accounts:report:read` |
| `fees-accounts.outstanding-dues` | Finance Staff | `GET /reports/outstanding` | `fees-accounts:report:read` |
| `fees-accounts.collection-vs-target` | Management | `GET /reports/collection-vs-target` | `fees-accounts:report:read` |

- **Data:** each widget reads through `src/api/client.ts`, a hand-written typed client that the generated client will replace.
- **States:** each widget shows loading, empty, and error with a retry. Until the backend is mounted, the error reads "Fee data is not available yet".
- **Tests:** `cd modules/finance-operations/fees-accounts/frontend && pnpm test` (vitest and Testing Library).

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers and tests |
| `frontend/` | Dashboard widgets and their tests |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
