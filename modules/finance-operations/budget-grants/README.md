# budget-grants

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend built; widgets next)

Annual budgets per budget head and cost centre, reappropriation, commitments and actual spend, externally funded
research grants with their own lines, funds received and utilisation certificates. Requirements:
[docs/prd.md](docs/prd.md); stories: [docs/user-stories.md](docs/user-stories.md).

## Scope
- **In scope:** what the institution plans to spend, what it has committed and spent against each line, and the money and paperwork of research grants.
- **Not in scope:**
  - buying (procurement);
  - salaries (hr-payroll);
  - fees (fees-accounts);
  - a general ledger.
  Spend arrives from procurement and hr-payroll by event, or is recorded by hand.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/budget-grants`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_budget_grants/domain/rules.py` | Exact money, available amount, percent used and thresholds, financial years, certificate due dates. Pure Python. |
| application | `application/service.py` | Budget heads; budgets (draft, submit, approve or return); reappropriation; availability and open lines for procurement; manual spend and its reversal; grants (sanction, revision, funds received, close); utilisation certificates (draft from the records, certify, mark submitted); `/me/grants`. |
| | `application/reports.py` | Budget against spend per head, with grant totals. |
| | `application/consumers.py` | Purchase orders issued, cancelled and paid; payroll paid. Idempotent by source; each event runs in its own organisation's scope. |
| | `application/jobs.py` | `run_daily`: certificate reminders, once per grant, due date and window. |
| infrastructure | `infrastructure/models.py` | 11 `budget_grants_*` tables, including `audit_entry`. Each has `organisation_id`; money is `Numeric(14, 2)`. |
| | `infrastructure/config.py` | `BUDGET_GRANTS_*` settings. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `budget_grants_0001` with its own version table. It applies the `tenant_isolation` policy on Postgres. |

Rules the code keeps:
- **Never spend past a line.** A line's available amount is its allocation less what is committed and spent. Manual spend can't exceed it. Procurement checks `/availability` before approving, and the commitment starts at the purchase order (#221).
- **Spend from other modules is always recorded.** It's real money, even if it takes a line past its allocation. Finance staff are told when a line crosses 80% and 100%, once each.
- **Nothing is deleted.** Manual entries are reversed with a reason, and approved budgets change only by reappropriation. Entries from other modules are reversed only by those modules' events.
- **Preparer and approver are different people,** for budgets, reappropriations and certificates. For a budget, the preparer is whoever last edited or submitted it.
- **Certificate due dates are period ends.** A grant starting 2026-04-01 with yearly certificates has due dates 2027-03-31 and so on, so a certificate for that period covers its due date. A returned certificate is redrafted, never certified as it stands.
- **Every change is audited.** An `audit_entry` row (actor, action, entity, id) is written in the same transaction. That covers changes from other modules' events too, until the audit SDK exists. Changes the contract defines events for also publish them to the outbox.
- **A grant with orders still committed can't be closed.** Release or pay them first.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/finance-operations/budget-grants/backend[test]"
pytest modules/finance-operations/budget-grants/backend
```

### Migrations

```sh
cd modules/finance-operations/budget-grants/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting:** mount `eos_budget_grants.api.router:router` under `/api/v1/budget-grants` and add the package to `apps/backend`.
- **CI:** add the backend to `tools/scripts/py-setup.sh` and to the pytest line in `.github/workflows/api.yml`.
- **Events:** until the event bus exists, relay the events in `consumes_events` to `application.consumers.handle(db, name, payload)`.
  Deliver one purchase order's events in order (issued, then paid or cancelled). If a paid invoice arrives before its
  order anyway, the spend is recorded and the late order commits only what is not yet paid, so nothing is counted twice.
- **Daily job:** until the scheduler exists, call `application.jobs.run_daily(db)` once a day.

### Assumptions to revisit
- **Departments:** `department_name` is empty until departments are available to modules.
- **Investigator names:** `name` is empty until identity names are available.
- **Certificate PDFs:** an approved certificate has no `document_id` until the documents SDK exists.
- **Payroll:** `net_total` is charged to one institution-wide salary head (PRD open question 3).

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
