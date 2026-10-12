# iqac-accreditation

**Domain:** governance
**Kind:** feature
**Status:** in-progress (contracts proposed)

IQAC data collection, NAAC/NBA metrics, evidence repository.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** the organisation's accreditation frameworks and their metrics; collection cycles; assigning metrics to
owners; responses (values or narratives) with evidence as links or references; review (accept or return); quality action
items; the counts behind the Governance widget `iqac-accreditation.action-items`. No accreditation content is built in.

**Not in scope:** evidence files, computing metric values from other modules, submitting to accrediting bodies' portals,
grades and peer team outcomes, statutory returns (regulatory-reports), reminders and timers.

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
