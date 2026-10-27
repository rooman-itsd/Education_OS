# asset-management

**Domain:** facilities
**Kind:** feature
**Status:** in-progress

Fixed asset register of the organisation: every long-lived, valuable thing it owns, where it is, who holds it, what it cost, what it is worth now and when it was last physically checked.

## Scope
Responsible for: asset categories, the asset register and tags, transfers between locations,
departments and custodians, physical verification cycles (the audit-due widget), depreciation runs,
and disposal with approval.

Not responsible for: lending and stock (`inventory-equipment`), repairs (`maintenance`), buying
(`procurement`), accounting ledgers (finance modules), AMC contracts (`amc-vendor-support`).
Those are linked by reference ids and events, never by foreign keys.

Requirements: [docs/prd.md](docs/prd.md).

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

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
