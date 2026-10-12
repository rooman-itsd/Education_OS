# grievance

**Domain:** governance
**Kind:** feature
**Status:** in-progress (contracts proposed)

SGRC, anti-ragging and POSH-ICC complaint intake and resolution.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** committees (SGRC, anti-ragging, ICC, ombudsperson) and their members; complaints on the student
grievance, ragging and sexual harassment tracks; acknowledgement, inquiry with committee-only proceedings, updates
between committee and complainant, decision, transfer, withdrawal; SGRC appeals to the ombudsperson; configurable due
dates worked out when read; open-case counts behind the Governance widget `grievance.open-by-committee` and the
Management widget `grievance.open`. Case content is visible only to the complainant and the committee handling it.

**Not in scope:** evidence attachments, respondent access, anonymous complaints, appeals on the ragging and sexual
harassment tracks, reminders, helpdesk tickets (helpdesk) and hostel discipline records (hostel).

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
