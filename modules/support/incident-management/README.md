# incident-management

**Domain:** support
**Kind:** feature
**Status:** in-progress (contracts proposed)

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
