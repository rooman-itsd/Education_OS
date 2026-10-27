# helpdesk

**Domain:** support
**Kind:** feature
**Status:** in-progress (backend and widget built and tested; registered in `apps/frontend` and `apps/backend`)

Ticketing for all user roles with categories and routing.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** tickets raised by any signed-in person or by an agent on their behalf; categories and
support queues; assignment and pick-up; public replies and internal notes; on hold, resolve, confirm,
reopen, auto-close and cancel; links to records in other modules; the open-by-priority counts behind the
Support Staff widget `helpdesk.open-by-priority`. Publishes ticket events that sla-management uses for
response and resolution clocks.

**Not in scope:** SLA targets, clocks and breaches (sla-management), repairs (maintenance), major
outages (incident-management), help articles (knowledge-base), vendor and AMC calls (amc-vendor-support),
grievances and RTI requests (grievance, rti).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_helpdesk` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/tickets.py`, `windows.py`, `stats.py`, `errors.py` | Ticket statuses and the moves between them, the reopen window and auto-close rule, the open-by-priority counts. Pure Python. |
| application | `application/service.py`, `jobs.py`, `access.py`, `errors.py`, `stats.py` | The use case behind every contract operation; permission keys and checks; errors with their HTTP status; the daily auto-close job. Every state change writes an audit entry and publishes its event from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the caller's organisation, `HELPDESK_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 25 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. |

Tables are prefixed `helpdesk_` and created by the module's own Alembic chain in `db/` (version table
`helpdesk_alembic_version`). Every table carries `organisation_id`; on Postgres each gets the `eos_core.rls`
row-level-security policy.

**Decisions by the architecture lead (Faizan) for #113:**
- **Shared schema with prefixed tables**, as the merged modules do, instead of a dedicated `helpdesk` Postgres
  schema (ADR-0002, ARCHITECTURE.md "Data", module-standard rule 2). `eos_core` (`rls.tenant_tables`, `init_db`)
  and the SQLite tests and local runs work with unqualified table names only.
- **Temporary audit table.** `helpdesk_audit_entry` holds one row per state change until the audit SDK and
  `platform/audit` exist (ARCHITECTURE.md "Every state change writes to `platform/audit`"). Known limitation: these
  rows are not in the platform audit trail. When the SDK ships, `_audit` in `application/service.py` calls it
  instead, and the table's rows are migrated or retired.

Who may act follows the contract as written: `helpdesk:ticket:work` for replies, notes, start, hold, resolve and
links on a ticket in the caller's queues (or any queue with `helpdesk:ticket:read-all`); the assignee rule applies
where the contract states one (PATCH priority, self pick-up through `/assign`). Details the contract leaves open are
noted in `application/service.py` where they are decided.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `support/helpdesk` in `apps/backend/config/modules.enabled.yaml`. From that list the module loader (#258) mounts
  `eos_helpdesk.api.router:router` at `/api/v1/helpdesk` behind the entitlement gate (`/api/v1/health` lists it);
  `tools/scripts/py-setup.sh` and the API image install the package; the API auto-deploy runs the Alembic chain in
  `db/` (after `infra/docker/stamp-chains.py`); and CI runs `backend/tests` and checks the chain's upgrade,
  row-level-security policies and downgrade on Postgres. If the package is not installed, the API does not start.
- Permissions come from the roles in the token. The profile roles `support-staff`, `org-admin` and `management` get
  the grants of `helpdesk-agent`, `helpdesk-admin` and `helpdesk-viewer` (contract 0.2.0); other profile roles, such
  as students raising their own tickets, get none yet (open question 13 in `docs/user-stories.md`).
- A daily call of `application.jobs.run_auto_close`, until `platform/scheduler` delivers `scheduler.job.due`.

## Frontend
`frontend/src/widgets/OpenByPriorityWidget.tsx` is the Support Staff widget `helpdesk.open-by-priority`
(`platform/identity/config/dashboards/support-staff.yaml` already lists it): open tickets in the caller's queues,
one row per priority, urgent first, with unassigned, assigned-to-you and on-hold counts, from
`GET /api/v1/helpdesk/stats/open-by-priority` (permission `helpdesk:ticket:read`). It uses `@eos/ui-kit` (`List`,
`ListRow`, `Badge`, `SkeletonLines`, `EmptyState`, `ErrorState`). While the API is not mounted or unreachable (404,
502, 503, network failure) it says "Helpdesk data is not available yet."; a 401 or 403 offers no retry.
`frontend/src/api/client.ts` is a small typed client matching the contract's `OpenByPriority`, until the repo has a
generated client. Tests are in `frontend/tests/` (Vitest and Testing Library).

The Support Staff dashboard shows the widget because `apps/frontend/config/modules.enabled.yaml` lists
`support/helpdesk`. Not built yet: links from each row to a filtered ticket list (that helpdesk page does not exist)
and the lead's `scope=all` view (no dashboard layout for a support lead exists; the widget uses the default
`my_queues`).

## Run the checks
```
cd modules/support/helpdesk/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
#   Python 3.12; dependencies plus the test extras (pytest, pyyaml, httpx, eos-testing, psycopg[binary])
cd modules/support/helpdesk/db && alembic upgrade head                   # own tables only; EOS_DATABASE_URL
ruff check --config tools/config/ruff.toml modules/support/helpdesk     # from the repo root
ruff format --config tools/config/ruff.toml --check modules/support/helpdesk
pnpm --filter @eos/helpdesk typecheck && pnpm --filter @eos/helpdesk test   # widget; after pnpm install at the root
```
Instead of `PYTHONPATH`, the module can be installed with its test extras, from the repo root:
`pip install ./packages/core ./packages/testing "./modules/support/helpdesk/backend[test]"`. It does not depend on
`packages/sdk`, which has no package yet. Tests use a throwaway SQLite file, never a real database.

Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when `HELPDESK_TEST_POSTGRES_URL` is set
to a superuser URL of a **throwaway** server (for example `postgres:16-alpine`, as CI and `infra/docker` use). It
creates its own database and a temporary role that is neither a superuser nor allowed to bypass RLS, checks the
forced `tenant_isolation` policy on all 7 tables, checks on 3 of them (`helpdesk_queue`,
`helpdesk_ticket_number_sequence`, `helpdesk_audit_entry`) that each organisation sees and writes only its own rows,
then drops both.
`HELPDESK_TEST_POSTGRES_URL` is a test setting, not module configuration, so it is not in `config/env.example`.

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
