# library

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract 0.2.0; backend, migrations, tests and the `library.loans` widget built;
not yet listed in the apps)

Catalogue, circulation, digital library, fines, reservations.

## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** catalogue of titles and copies; members and loan policies; circulation (issue, return,
renew, lost); reservations and holds; fines paid at the desk or waived; a list of digital resources
(links only). Publishes fine events that fees-accounts may use to invoice fines.

**Not in scope:** buying books and subscriptions (procurement), hosting digital content, inter-library
loans and RFID gates (later integrations), reading-room seat booking (facility-booking).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widget: `library.loans` (Student dashboard), exported from `frontend/src/widgets/index.ts`
- Consumes: `fees-accounts.invoice.paid` (a fine invoiced in fees-accounts and paid there is marked paid here)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widget. No platform service is called directly yet: events go to the outbox, and the
  daily jobs (`backend/src/eos_library/application/jobs.py`, `run_daily`: flag overdue loans, expire uncollected
  holds) wait for `platform/scheduler` to call them.
- The event-bus relay delivers `fees-accounts.invoice.paid` through the `eos.event_consumers` entry point
  (`eos_library.application.consumers:CONSUMERS`); a host without the relay can call `consumers.handle`.
- The API router is `eos_library.api.router:router`, mounted under `/api/v1/library` by the module loader from
  `apps/backend/config/modules.enabled.yaml`. The widgets are registered from `apps/frontend/config/modules.enabled.yaml`.

## Run the checks
```
pip install -e modules/campus-life/library/backend[test]      # into the repo .venv
cd modules/campus-life/library/backend && python -m pytest -q # throwaway SQLite, never a real database
pnpm --filter @eos/library typecheck && pnpm --filter @eos/library test
cd modules/campus-life/library/db && alembic upgrade head     # own tables and library_alembic_version only
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
