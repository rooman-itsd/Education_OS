# athlete-performance

**Domain:** sports
**Kind:** feature
**Status:** in-progress

Athlete profiles, performance metrics, fitness testing, benchmarks.

## Scope
Responsible for: the sports catalogue (disciplines, metric definitions, fitness tests), athlete sports profiles,
performance results and their history, fitness assessments, benchmarks and the comparison with them, fitness
clearance (status only) and the squad summary report.

Not responsible for: tournaments and fixtures (`tournament-events`), training plans and video
(`training-video-analysis`), medical records, injuries and nutrition (`sports-nutrition-health`), student records
(`student-information`) and sign-in (`platform/identity`). Those are linked by reference ids and events, never by
foreign keys.

Athletes see only their own profile, results, assessments, history and clearance; coaches, medical staff and
administrators see their organisation's athletes (`application/service.py`).

Requirements: [docs/prd.md](docs/prd.md). Tables: [docs/data-model.md](docs/data-model.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens) and, for its
tests, `packages/testing`. The backend is `eos_athlete_performance.api.router:router`; its Alembic chain is `db/`. This module must not import code from any other module under `modules/`.

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
