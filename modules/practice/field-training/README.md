# field-training

**Domain:** practice
**Kind:** feature
**Status:** in-progress (contracts proposed)

Field training placements: clinical rotations, teaching practice, farm rotations, internships, court visits.


## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md).

Generic "Field training" pattern used by every academy type. Labels come from the academy profile
vocabulary (`field-training.placement`, `field-training.site`, `field-training.supervisor`); the module
names no field.

**In scope:** host sites and their supervisors; openings with seats, period and required hours;
placements by assignment or application; the logbook of hours and activities with supervisor
verification; mid and final assessment outcome; completion and withdrawal.

**Not in scope:** paid job placement drives (placement-career), rubric-based skill assessment
(skill-progress), class attendance (timetable-attendance), site agreements as documents
(platform/documents), and any field-specific rule (a profile setting or a specialized module).

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
