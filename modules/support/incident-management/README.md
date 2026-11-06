# incident-management

**Domain:** support
**Kind:** feature
**Status:** in-progress (backend and widget built and tested; not yet listed in `modules.enabled.yaml`)

Incident and problem records, root cause analysis.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** incidents (service disruptions) with severity, lead, responders, a timeline and references to
related records in other modules; problems behind one or more incidents, with known errors and workarounds;
root-cause analysis (draft and publish); corrective actions with owners and due dates; the open-incident counts
behind the Support Staff widget `incident-management.open`.

**Not in scope:** individual requests (helpdesk), SLA clocks (sla-management), repairs (maintenance), asset
records (asset-management), vendor and AMC calls (amc-vendor-support), knowledge articles (knowledge-base), a
status board or broadcast to affected users, reminders and timers.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_incident_management` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/incidents.py`, `problems.py`, `stats.py`, `errors.py` | Incident statuses and the moves between them (resolution summary to resolve, note to cancel or reopen); problem statuses (workaround for a known error, published RCA to resolve); RCA draft and publish; corrective-action statuses and overdue worked out when read; the open-incident counts. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys and checks; errors with their HTTP status. Every state change, timeline update, reference change, problem link, RCA change and action change writes an audit entry, and the six events of `contracts/events.yaml` go to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the caller's organisation, per-organisation numbering, `INCIDENT_MANAGEMENT_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 20 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. |

Tables are prefixed `incident_management_` and created by the module's own Alembic chain in `db/` (revision
`incident_management_0001`, version table `incident_management_alembic_version`). Every table carries
`organisation_id`; on Postgres each gets the `eos_core.rls` row-level-security policy. As in amc-vendor-support and
helpdesk, a temporary `incident_management_audit_entry` table holds one row per change until the audit SDK and
`platform/audit` exist; `_audit` in `application/service.py` then calls the SDK instead.

Incident and problem numbers (`INC-000001`, `PRB-000001`) are counted per organisation in a locked sequence row that
is first created with `INSERT ... ON CONFLICT DO NOTHING`. Saving an RCA and recording a reference lock the parent row
first, so two requests at the same moment run one after the other. Request values are bounded to what the columns hold
(titles 200, service labels 80, text 20 000 characters; date-times and dates between 2000 and 2100), so oversized or
out-of-range values are a 422. Details the contract leaves open are noted in `application/service.py` where they are
decided.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `support/incident-management` in `apps/backend/config/modules.enabled.yaml`, added in a later pull request of #342.
  From that list the module loader mounts `eos_incident_management.api.router:router` at
  `/api/v1/incident-management`, the API image installs the package, the auto-deploy runs the Alembic chain and CI
  runs `backend/tests`. Until then the module's tests run only as shown below.
- Permissions come from the roles in the token. The `support-staff` profile role gets the grants of
  `incident-management-responder` through its dashboard layout, so it can report and work incidents, read problems
  and see the widget. No layout grants `incident-management-problem-manager` or `incident-management-viewer` yet
  (the PRD names a support lead, management and org-admin), so on a live site nobody can open problems or write RCAs
  until a layout grants them.

## Frontend
`frontend/src/widgets/OpenIncidentsWidget.tsx` is the Support Staff widget `incident-management.open`
(`platform/identity/config/dashboards/support-staff.yaml` already lists it): incidents in open, investigating or
mitigated, one row per severity, critical first, each with "N open", and a line with how many are not yet picked up,
investigating and mitigated, from `GET /api/v1/incident-management/stats/open` (permission
`incident-management:incident:read`). It uses `@eos/ui-kit` (`List`, `ListRow`, `Badge`, `SkeletonLines`,
`EmptyState`, `ErrorState`). While the API is not mounted or unreachable (404, 502, 503, network failure) it says
"Incident data is not available yet."; a 401 or 403 offers no retry. `frontend/src/api/client.ts` is a small typed
client matching the contract's `OpenCounts`, until the repo has a generated client. Tests are in `frontend/tests/`
(Vitest and Testing Library).

The dashboard shows the widget once `apps/frontend/config/modules.enabled.yaml` lists `support/incident-management`.

## Run the checks
```
cd modules/support/incident-management/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
#   Python 3.12; dependencies plus the test extras (pytest, pyyaml, httpx, eos-testing, psycopg[binary])
cd modules/support/incident-management/db && alembic upgrade head                  # own tables only; EOS_DATABASE_URL
ruff check --config tools/config/ruff.toml modules/support/incident-management    # from the repo root
ruff format --config tools/config/ruff.toml --check modules/support/incident-management
pnpm --filter @eos/incident-management typecheck && pnpm --filter @eos/incident-management test   # widget
```
Instead of `PYTHONPATH`, the module can be installed with its test extras, from the repo root:
`pip install ./packages/core ./packages/testing "./modules/support/incident-management/backend[test]"`. It does not
depend on `packages/sdk`, which has no package yet. Tests use a throwaway SQLite file, never a real database.

Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when
`INCIDENT_MANAGEMENT_TEST_POSTGRES_URL` is set to a superuser URL of a **throwaway** server (for example
`postgres:16-alpine`). It creates its own database and a temporary role that is neither a superuser nor allowed to
bypass RLS, checks the forced `tenant_isolation` policy on all 8 tables, checks on every table that each organisation
sees and writes only its own rows, checks that two first numbers and two first RCA drafts at the same moment do not
collide, then drops both. It is a test setting, not module configuration, so it is not in `config/env.example`.

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
