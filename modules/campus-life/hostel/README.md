# hostel

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract 0.2.0 reviewed; backend, migrations, tests and the `hostel.notices` widget built;
not yet mounted in `apps/`)

Room allocation, mess, visitors, discipline and fee linkage.

## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** hostels, rooms and beds; room requests, allocation, check-in and check-out; mess menu;
leave requests as gate passes (security records departure and return); visitor log; discipline incidents; notices to residents. Publishes allocation
events that fees-accounts may use to raise hostel fee invoices.

**Not in scope:** charging and collecting hostel or mess fees (fees-accounts), mess inventory and
purchasing (inventory-equipment, procurement), room repairs (maintenance), guest-room booking
(facility-booking).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widget: `hostel.notices` (Student dashboard), exported from `frontend/src/widgets/index.ts`


## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widget. No platform service is called directly yet: events go to the outbox, and
  the overdue-leave job (`backend/src/eos_hostel/application/jobs.py`, `flag_overdue_leave`) waits for
  `platform/scheduler` to call it daily.
- The API router is `eos_hostel.api.router:router`, to be mounted under `/api/v1/hostel`.

## Run the checks
```
pip install -e modules/campus-life/hostel/backend[test]       # into the repo .venv
cd modules/campus-life/hostel/backend && python -m pytest -q  # throwaway SQLite, never a real database
pnpm --filter @eos/hostel typecheck && pnpm --filter @eos/hostel test
cd modules/campus-life/hostel/db && alembic upgrade head      # own tables and hostel_alembic_version only
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
