# regulatory-reports

**Domain:** governance
**Kind:** feature
**Status:** in-progress (backend and widgets built and tested; not yet listed in `modules.enabled.yaml`)

UGC, AISHE, NIRF and other statutory reporting.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** the organisation's own list of statutory reporting obligations; filings per period with preparation,
review, submission and acknowledgement; due and overdue filings worked out when read; the statistics behind the widget
`regulatory-reports.due` and the calendar behind `regulatory-reports.compliance-calendar`. No regulator, return, form or
deadline is built in, and the module is field-neutral.

**Not in scope:** compiling return data from other modules, analytics and warehousing (platform/reporting), automatic
recurrence and reminders, evidence files, regulators' portals, computing payroll and tax returns (hr-payroll).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_regulatory_reports` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/filings.py`, `due.py`, `errors.py` | Filing statuses and the moves between them, periods and dates, what counts as due soon and overdue. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys and checks (a preparer sees only their own filings); errors with their HTTP status. Every change writes an audit entry; submission and acknowledgement publish their events from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the caller's organisation, `REGULATORY_REPORTS_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 13 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. A NUL character in a request is a 404 or 422, never a 500 on Postgres. |

Tables are prefixed `regulatory_reports_` and created by the module's own Alembic chain in `db/` (revision
`regulatory_reports_0001`, version table `regulatory_reports_alembic_version`). Every table carries
`organisation_id`; on Postgres each gets the `eos_core.rls` row-level-security policy. As in the support modules, a
temporary `regulatory_reports_audit_entry` table holds one row per change until the audit SDK and `platform/audit`
exist. Recurrence is informational (PRD open question 3): filings are created per period by the coordinator, and no
due date is worked out from it.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `governance/regulatory-reports` in `apps/backend/config/modules.enabled.yaml` and
  `apps/frontend/config/modules.enabled.yaml`, in a later pull request of #343.
- Permissions come from the roles in the token. The layouts already grant the module roles: Governance
  `regulatory-reports-coordinator`, Management `regulatory-reports-viewer`, Hospital Coordinator and Research Office
  `regulatory-reports-preparer`.

## Frontend
- `frontend/src/widgets/DueWidget.tsx` is `regulatory-reports.due` (Governance, Hospital Coordinator, Research Office):
  overdue and due-soon counts and the soonest filings, each with "Overdue by N days", "Due today" or "Due in N days",
  from `GET /stats/due` (permission `regulatory-reports:stats:read`). "Mine" is the default; "All" also needs
  `regulatory-reports:data:read`.
- `frontend/src/widgets/CalendarWidget.tsx` is `regulatory-reports.compliance-calendar` (Management): filings due in
  the next 90 days by due date, with the obligation, authority, period and status in words, from `GET /calendar`.

Both use `@eos/ui-kit` and the widget error convention: 404, 502, 503 or a network failure is "Regulatory report data is
not available yet." with retry; a 401 or 403 offers no retry. `frontend/src/api/client.ts` is a small typed client
matching the contract until the repo has a generated one. Tests are in `frontend/tests/` (Vitest and Testing Library).

## Run the checks
```
cd modules/governance/regulatory-reports/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
ruff check --config tools/config/ruff.toml modules/governance/regulatory-reports    # from the repo root
pnpm --filter @eos/regulatory-reports typecheck && pnpm --filter @eos/regulatory-reports test
```
Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when
`REGULATORY_REPORTS_TEST_POSTGRES_URL` is set to a superuser URL of a **throwaway** server. It creates its own database
and a temporary role that is neither a superuser nor allowed to bypass RLS, checks the forced `tenant_isolation` policy
on every table and each organisation's isolation, then drops both.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
