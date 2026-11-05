# projects

**Domain:** practice
**Kind:** feature
**Status:** in-progress (contract 0.1.0; backend, migrations, tests and four widgets built; not yet listed in the apps)

Projects with milestones, teams and reviews: capstone, film, live business, research, artwork.


## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md). Stories:
[docs/user-stories.md](docs/user-stories.md).

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
- Dashboard widgets, exported from `frontend/src/widgets/index.ts`:

| Widget | Permission | Endpoint |
|---|---|---|
| `projects.my-projects` | `projects:self:read` | `GET /me/projects` |
| `projects.milestones-due` | `projects:self:read` | `GET /me/milestones` |
| `projects.to-review` | `projects:guidance:read` | `GET /me/reviews` |
| `projects.active` | `projects:guidance:read` | `GET /projects?status=active` |

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widgets. No platform service is called directly yet: events go to the outbox, submission
  files are uploaded through platform/documents and only their ids are stored here, and the daily job
  (`backend/src/eos_projects/application/jobs.py`, `run_daily`: overdue milestones) waits for `platform/scheduler`.
- The API router is `eos_projects.api.router:router`, mounted under `/api/v1/projects` by the module loader from
  `apps/backend/config/modules.enabled.yaml`. The widgets are registered from `apps/frontend/config/modules.enabled.yaml`.

## Run the checks
```
pip install -e modules/practice/projects/backend[test]          # into the repo .venv
cd modules/practice/projects/backend && python -m pytest -q     # throwaway SQLite, never a real database
pnpm --filter @eos/projects typecheck && pnpm --filter @eos/projects test
cd modules/practice/projects/db && alembic upgrade head         # own tables and projects_alembic_version only
```

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
