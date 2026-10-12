# amc-vendor-support

**Domain:** support
**Kind:** feature
**Status:** in-progress (contracts proposed)

AMC contracts, vendor support engagements, renewals.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** AMC contracts with vendors (period, coverage type, value, response terms, contacts) and the items they
cover; activation, renewal and early termination; expiring and expired contracts worked out when read; support calls
and service visits (engagements) under a contract; the coverage lookup for other modules' screens; the statistics
behind the Support Staff widget `amc-vendor-support.contracts-expiring`.

**Not in scope:** the vendor master, vendor approval and blacklisting, purchase orders, invoices and payments
(procurement); repairs (maintenance); the asset register and warranties (asset-management); SLA clocks
(sla-management); contract documents; renewal reminders.

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
