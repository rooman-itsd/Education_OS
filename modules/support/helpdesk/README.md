# helpdesk

**Domain:** support
**Kind:** feature
**Status:** in-progress (contracts proposed)

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
