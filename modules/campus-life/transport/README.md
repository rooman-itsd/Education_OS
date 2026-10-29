# transport

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract 0.2.0; backend, migrations, tests and the `transport.notices` widget built;
registered in `apps/backend` and `apps/frontend`)

Routes, vehicles, passes, driver management, tracking.

## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** stops and routes; vehicles, drivers and their compliance dates; assigning vehicles and
drivers to routes; pass requests and passes; trips with live position and delay; service notices.
Publishes pass events that fees-accounts may use to raise transport fee invoices.

**Not in scope:** charging and collecting transport fees (fees-accounts), fuel and parts (inventory-equipment,
procurement), vehicle repairs (maintenance), driver payroll (hr-payroll), a GPS device adapter (a later
integration).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widget: `transport.notices` (Student dashboard), exported from `frontend/src/widgets/index.ts`

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widget. No platform service is called directly yet: events go to the outbox, and the
  daily jobs (`backend/src/eos_transport/application/jobs.py`, `run_daily`: expire passes, flag expiring
  documents, purge positions) wait for `platform/scheduler` to call them.
- The API router is `eos_transport.api.router:router`, mounted under `/api/v1/transport` by the module loader from
  `apps/backend/config/modules.enabled.yaml`. The widgets are registered from `apps/frontend/config/modules.enabled.yaml`.

## Run the checks
```
pip install -e modules/campus-life/transport/backend[test]       # into the repo .venv
cd modules/campus-life/transport/backend && python -m pytest -q  # throwaway SQLite, never a real database
pnpm --filter @eos/transport typecheck && pnpm --filter @eos/transport test
cd modules/campus-life/transport/db && alembic upgrade head      # own tables and transport_alembic_version only
```

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
