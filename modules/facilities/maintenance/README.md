# maintenance

**Domain:** facilities
**Kind:** feature
**Status:** in-progress

Keeps buildings, spaces and equipment working. Anyone reports a fault; maintenance staff triage it, assign it to a technician or vendor, track it against response and resolution targets and record the cost. Preventive schedules raise tickets on their own.

## Scope
Responsible for: ticket categories, tickets (corrective, preventive, inspection) on an asset,
resource, inventory unit or location, assignment to technicians or vendors, SLA tracking, work log
and costs, resolution and reopen, preventive schedules.

Not responsible for: general service requests (`helpdesk`), vendor contracts and AMC renewals
(`amc-vendor-support`), issuing spare parts (`inventory-equipment`), purchasing (`procurement`),
taking a target out of use (its own module, reacting to this module's events).

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
