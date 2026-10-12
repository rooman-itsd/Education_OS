# sla-management

**Domain:** support
**Kind:** feature
**Status:** in-progress (contracts proposed)

SLA definitions, timers, escalation and breach tracking.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** business-hours calendars; SLA policies per helpdesk priority and category with response and
resolution targets, warning thresholds, pausing hold reasons and escalation levels; response and resolution
clocks per helpdesk ticket, driven by helpdesk's ticket events; warnings, breaches and escalation notices
through notification; the breach counts behind the Support Staff widget `sla-management.breaches`.

**Not in scope:** tickets and their status (helpdesk), SLAs of maintenance, incident-management and
amc-vendor-support, deadlines on approval steps (workflow), escalation by reassignment or approval.

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
