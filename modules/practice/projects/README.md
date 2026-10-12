# projects

**Domain:** practice
**Kind:** feature
**Status:** in-progress (contracts proposed)

Projects with milestones, teams and reviews: capstone, film, live business, research, artwork.


## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md).

Generic "Projects" pattern used by every academy type. Labels come from the academy profile vocabulary
(`projects.project`, `projects.milestone`, `projects.guide`); the module names no field.

**In scope:** proposals and approval; teams with a lead; guides; milestones with versioned submissions
and reviews; final submission and evaluation; cancellation.

**Not in scope:** grants and budgets (budget-grants), rubric-based skill assessment (skill-progress), course
grades (examinations), showcasing and staging finished work (portfolio, productions), plagiarism, ethics and
viva workflows (later integrations or a specialized module).

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
