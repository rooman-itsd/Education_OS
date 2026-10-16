# inventory-equipment

**Domain:** facilities
**Kind:** feature
**Status:** in-progress (backend built; widgets next)

Generic inventory pattern (ADR-0004). Keeps track of movable things an organisation stores, lends and uses up: catalogue, individually tagged units, stock per store, the stock ledger, low stock and loans. Each academy names the item in its profile vocabulary (`inventory-equipment.item`), for example "Instrument", "Costume / prop" or "Lab equipment".

## Scope
Responsible for: categories and items, units with tag and condition, store locations, stock
levels and the append-only stock ledger, low-stock detection, loans (request, approval, hand-out,
return, extension, overdue, lost).

Not responsible for: fixed assets and depreciation (`asset-management`), repairs (`maintenance`),
purchasing (`procurement`), booking spaces (`facility-booking`), library books (`library`).
Those modules react to this module's events.

Requirements: [docs/prd.md](docs/prd.md). Stories: [docs/user-stories.md](docs/user-stories.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

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

## Backend
Python package `eos_inventory_equipment` in `backend/src/`, in four layers:

| Layer | Path | What is in it |
|---|---|---|
| domain | `domain/rules.py` | Loan rules, stock arithmetic, low-stock crossing, loan status from its lines. Pure Python. |
| application | `application/service.py`, `jobs.py` | Use cases; every quantity change writes the ledger and every state change publishes its event to the outbox. Scheduler sweeps (overdue, pickup expiry). |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | Tables (`inventory_equipment_*`, `organisation_id` on every one), tenant-scoped queries with row locks, `INVENTORY_EQUIPMENT_*` settings. |
| api | `api/router.py`, `deps.py`, `schemas.py` | `router: APIRouter`, mounted by the host under `/api/v1/inventory-equipment`; token check and permissions. |

Run the tests alone (they always use a throwaway SQLite file, never a real database):

```bash
pip install -e packages/core -e packages/testing -e "modules/facilities/inventory-equipment/backend[test]"
cd modules/facilities/inventory-equipment/backend && python -m pytest
```

Migrations (own chain, own version table `inventory_equipment_alembic_version`; RLS policies on Postgres):

```bash
cd modules/facilities/inventory-equipment/db && alembic upgrade head   # uses EOS_DATABASE_URL
```

### Needs from the host repo
- `packages/core` (`eos_core`) and, for tests, `packages/testing` (`eos_testing`).
- Mount `eos_inventory_equipment.api.router:router` under `/api/v1/inventory-equipment` in `apps/backend`, and add
  `facilities/inventory-equipment` to `apps/frontend/config/modules.enabled.yaml` once the widgets ship.
- Users need the module roles (`inventory-equipment-borrower`, `-approver`, `-manager`) in their token roles, or an
  identity mapping from academy roles to them.
- A scheduler that calls `application.jobs.run_sweeps` every few minutes, until `platform/scheduler` exists.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
