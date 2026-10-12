# regulatory-reports

**Domain:** governance
**Kind:** feature
**Status:** in-progress (contracts proposed)

UGC, AISHE, NIRF and other statutory reporting.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** the organisation's own list of statutory reporting obligations; filings per period with preparation,
review, submission and acknowledgement; due and overdue filings worked out when read; the statistics behind the widget
`regulatory-reports.due` and the calendar behind `regulatory-reports.compliance-calendar`. No regulator, return, form or
deadline is built in, and the module is field-neutral.

**Not in scope:** compiling return data from other modules, analytics and warehousing (platform/reporting), automatic
recurrence and reminders, evidence files, regulators' portals, computing payroll and tax returns (hr-payroll).

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
